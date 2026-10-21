"""(1.3) The check that every DNS server of a full tunnel is reached through the tunnel, against the kernel's real
policy routing. Run as root in an empty network namespace:  unshare -n python3 -I tests/vpn_dns_route_netns.py build/vv-vpn-helper
A local network 192.168.1.0/24 and a tunnel interface routed the way wg-quick routes 0.0.0.0/0 (table 51820, "not fwmark",
"suppress_prefixlength 0"; veth pairs stand in for the network card and for WireGuard): the local network stays outside
the tunnel, so a DNS server there would be asked outside it."""
import importlib.machinery, importlib.util, subprocess, sys
H = sys.argv[1]
l = importlib.machinery.SourceFileLoader("helper", H); sp = importlib.util.spec_from_loader("helper", l)
h = importlib.util.module_from_spec(sp); l.exec_module(h)
def sh(c): subprocess.run(c, shell=True, check=True)
# a LAN (192.168.1.0/24, router .1) and a tunnel interface "pvpn" routed the way wg-quick does it for 0.0.0.0/0
sh("ip link set lo up; ip link add lan0 type veth peer name lan1; ip addr add 192.168.1.20/24 dev lan0; ip link set lan0 up; ip link set lan1 up")
sh("ip route add default via 192.168.1.1 dev lan0")
sh("ip link add pvpn type veth peer name pvpn1; ip addr add 10.2.0.2/32 dev pvpn; ip link set pvpn up; ip link set pvpn1 up")
sh("ip -4 route add 0.0.0.0/0 dev pvpn table 51820; ip -4 rule add not fwmark 51820 table 51820; "
   "ip -4 rule add table main suppress_prefixlength 0")
ok = 0
def check(c, m):
    global ok
    if not c: print("FAIL", m); sys.exit(1)
    ok += 1
check(h.dns_outside("pvpn", ["10.2.0.1", "1.1.1.1"]) == [], "VPN DNS and a public DNS go through the tunnel")
check(h.dns_outside("pvpn", ["192.168.1.1"]) == ["192.168.1.1"], "the router's DNS is outside the tunnel")
check(h.dns_outside("pvpn", ["127.0.0.1"]) == ["127.0.0.1"], "a local resolver is outside the tunnel")
check(h.dns_outside("other", ["10.2.0.1"]) == ["10.2.0.1"], "another interface name")
# a VPN DNS inside the local network's range: the local network wins, outside the tunnel
check(h.dns_outside("pvpn", ["192.168.1.53"]) == ["192.168.1.53"], "VPN DNS inside the LAN range")
# a tunnel Address /16 (connected route in the main table): its DNS inside it goes through the tunnel
sh("ip addr add 10.14.0.2/16 dev pvpn")
check(h.dns_outside("pvpn", ["10.14.0.1", "162.252.172.57"]) == [], "Address /16 style")
print(f"dns route: {ok} checks passed")
