#!/bin/bash
# runs inside: unshare -n (the "host" network namespace); makes a LAN namespace and a VM namespace
export PATH=/usr/sbin:/usr/bin
set -u
unshare -n sleep 300 & LAN=$!; unshare -n sleep 300 & VM=$!; sleep 0.5
ip link set lo up
ip link add eth0 type veth peer name lan0; ip link set lan0 netns $LAN
ip addr add 10.9.0.2/24 dev eth0; ip link set eth0 up
nsenter -t $LAN -n sh -c 'ip link set lo up; ip addr add 10.9.0.1/24 dev lan0; ip link set lan0 up; ip route add default via 10.9.0.2'
ip link add virbr0 type bridge; ip addr add 192.168.122.1/24 dev virbr0; ip link set virbr0 up
ip link add vnet0 type veth peer name vm0; ip link set vm0 netns $VM; ip link set vnet0 master virbr0 up
nsenter -t $VM -n sh -c 'ip link set lo up; ip addr add 192.168.122.10/24 dev vm0; ip link set vm0 up; ip route add default via 192.168.122.1'
ip link add proton-ch1 type veth peer name tunpeer; ip addr add 10.2.0.2/32 dev proton-ch1; ip link set proton-ch1 up; ip link set tunpeer up
ip route add default via 10.9.0.1
sysctl -q net.ipv4.ip_forward=1
# UDP echo on the LAN side, port 51820 (plays the VPN server) and 5353 (anything else)
nsenter -t $LAN -n python3 -c '
import socket, threading
def srv(p):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("10.9.0.1", p))
    while True:
        d, a = s.recvfrom(100); s.sendto(d, a)
for p in (51820, 5353): threading.Thread(target=srv, args=(p,), daemon=True).start()
import time; time.sleep(60)' & sleep 0.5
udp() { python3 -c '
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(1)
try:
    s.sendto(b"x", (sys.argv[1], int(sys.argv[2]))); s.recvfrom(10); print("open")
except OSError: print("blocked")' "$1" "$2"; }
p() { ping -c1 -W1 "$@" >/dev/null 2>&1 && echo open || echo blocked; }
report() {
  echo "  host -> LAN ping                 : $(p 10.9.0.1)"
  echo "  host -> VPN server udp 51820     : $(udp 10.9.0.1 51820)"
  echo "  host -> LAN udp 5353 (not server): $(udp 10.9.0.1 5353)"
  echo "  VM   -> LAN ping (forwarded)     : $(nsenter -t $VM -n ping -c1 -W1 10.9.0.1 >/dev/null 2>&1 && echo open || echo blocked)"
  echo "  VM   -> this PC ping (virbr0)    : $(nsenter -t $VM -n ping -c1 -W1 192.168.122.1 >/dev/null 2>&1 && echo open || echo blocked)"
}
echo "without kill switch:"; report
nft -f /tmp/ks-lan.nft; echo "with kill switch (server 10.9.0.1:51820):"; report
nft delete table inet vv_killswitch; echo "released:"; report
kill $LAN $VM 2>/dev/null
