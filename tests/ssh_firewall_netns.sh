#!/bin/bash
# tests/ssh_firewall_netns.sh DEBIAN13_ROOT  (as root; use a THROWAWAY Debian 13 root with openssh-server: a user
# "tester" and the 1.3 sshd settings are written into it)
# Two network namespaces joined by a veth pair: vvs = the VaeVictis side (the root's sshd behind the 1.3 firewall),
# vvc = a client. Checks: port closed until ssh_open has it, ed25519 in / RSA out / sftp refused, rate limit,
# port closed again after removal while the open session stays.
set -u
D=$(realpath "${1:?usage: ssh_firewall_netns.sh DEBIAN13_ROOT}")
HERE=$(cd "$(dirname "$0")" && pwd)
S=$(mktemp -d)
[ -x "$D/usr/sbin/sshd" ] || { echo "no sshd in $D" >&2; exit 1; }
# the 1.3 rules and sshd settings, from vv-harden itself (test mode, into a temporary folder)
mkdir -p "$S/fake/etc/systemd/system" "$S/fake/etc/ssh"; echo 13 > "$S/fake/etc/debian_version"
( cd "$HERE/../build" && VV_CHROOT="$S/fake" VV_SKIP_CHROOT=1 ./vv-harden >/dev/null )
cp "$S/fake/etc/nftables.conf" "$S/rules13.nft"
install -d "$D/etc/ssh/sshd_config.d"; cp "$S/fake/etc/ssh/sshd_config.d/10-vaevictis.conf" "$D/etc/ssh/sshd_config.d/"
pass=0; fail=0
ok()  { echo "OK   $*"; pass=$((pass+1)); }
bad() { echo "FAIL $*"; fail=$((fail+1)); }
cleanup() { ip netns pids vvs 2>/dev/null | xargs -r kill 2>/dev/null; ip netns del vvs 2>/dev/null; ip netns del vvc 2>/dev/null
            umount -l $D/dev 2>/dev/null; umount -l $D/proc 2>/dev/null; true; }
trap 'cleanup; rm -rf "$S"' EXIT
cleanup
ip netns add vvs; ip netns add vvc
ip link add vva type veth peer name vvb
ip link set vva netns vvs; ip link set vvb netns vvc
ip -n vvs addr add 10.99.0.1/24 dev vva; ip -n vvs link set vva up; ip -n vvs link set lo up
ip -n vvc addr add 10.99.0.2/24 dev vvb; ip -n vvc link set vvb up; ip -n vvc link set lo up
ip netns exec vvs nft -f $S/rules13.nft || { echo "rules not loaded"; exit 1; }

mount --rbind /dev $D/dev; mount -t proc proc $D/proc
mkdir -p $D/run/sshd
chroot $D /bin/sh -c 'getent group sshusers >/dev/null || groupadd -r sshusers; id tester >/dev/null 2>&1 || useradd -m -s /bin/bash -G sshusers tester; passwd -d tester >/dev/null 2>&1; usermod -p "*" tester'
rm -rf $S/sshkeys; mkdir -p $S/sshkeys
ssh-keygen -q -t ed25519 -N "" -f $S/sshkeys/ed
ssh-keygen -q -t rsa -b 3072 -N "" -f $S/sshkeys/rsa
rm -f $D/tmp/hostkey $D/tmp/hostkey.pub; ssh-keygen -q -t ed25519 -N "" -f $D/tmp/hostkey
install -d -m 700 $D/home/tester/.ssh
cat $S/sshkeys/ed.pub $S/sshkeys/rsa.pub > $D/home/tester/.ssh/authorized_keys
chroot $D chown -R tester: /home/tester/.ssh; chmod 600 $D/home/tester/.ssh/authorized_keys
ip netns exec vvs chroot $D /usr/sbin/sshd -D -e -h /tmp/hostkey -o HostKey=/tmp/hostkey > $S/sshd.log 2>&1 &
sleep 1.5
SSH=(ssh -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=3 -p 2299)

ip netns exec vvc timeout 5 bash -c '</dev/tcp/10.99.0.1/2299' 2>/dev/null && bad "port reachable before ssh_open has it" || ok "port closed while ssh_open is empty"
ip netns exec vvs nft add element inet vv_filter ssh_open { 2299 }
out=$(ip netns exec vvc "${SSH[@]}" -i $S/sshkeys/ed tester@10.99.0.1 'echo in-as-$(id -un)' 2>&1)
[[ "$out" == *in-as-tester* ]] && ok "ed25519 key logs in (client: $(ssh -V 2>&1 | cut -d, -f1))" || bad "ed25519 login: $out"
kex=$(ip netns exec vvc "${SSH[@]}" -v -i $S/sshkeys/ed tester@10.99.0.1 true 2>&1 | grep -o 'kex: algorithm: [^ ]*' | head -1)
echo "     $kex"
out=$(ip netns exec vvc "${SSH[@]}" -o IdentitiesOnly=yes -i $S/sshkeys/rsa tester@10.99.0.1 true 2>&1)
[[ "$out" == *"Permission denied"* ]] && ok "RSA key refused" || bad "RSA: $out"
out=$(echo "ls" | ip netns exec vvc sftp -F /dev/null -b - -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -P 2299 -i $S/sshkeys/ed tester@10.99.0.1 2>&1)
[[ $? -ne 0 ]] && ok "sftp refused ($(echo "$out" | tail -1))" || bad "sftp worked: $out"
echo hi > $S/sshkeys/f.txt
ip netns exec vvc scp -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -P 2299 -i $S/sshkeys/ed $S/sshkeys/f.txt tester@10.99.0.1:/tmp/ >/dev/null 2>&1 && bad "scp (sftp mode) worked" || ok "scp in sftp mode refused"
ip netns exec vvc scp -O -F /dev/null -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -P 2299 -i $S/sshkeys/ed $S/sshkeys/f.txt tester@10.99.0.1:/tmp/ >/dev/null 2>&1 && ok "scp -O still works (shell command, as documented)" || echo "     note: scp -O did not work either"

# rate limit: the logins above used new connections; wait for the meter to refill, then 8 quick connects
sleep 61
n=0; for i in $(seq 8); do ip netns exec vvc timeout 2 bash -c '</dev/tcp/10.99.0.1/2299' 2>/dev/null && n=$((n+1)); done
[ "$n" -ge 3 ] && [ "$n" -le 5 ] && ok "rate limit: $n of 8 quick new connections accepted" || bad "rate limit: $n of 8 accepted"

# port closed again while an open session keeps working
sleep 61
ip netns exec vvc "${SSH[@]}" -i $S/sshkeys/ed tester@10.99.0.1 'sleep 6; echo still-here' > $S/sshkeys/held.out 2>&1 &
sleep 2
ip netns exec vvs nft delete element inet vv_filter ssh_open { 2299 }
ip netns exec vvc timeout 4 bash -c '</dev/tcp/10.99.0.1/2299' 2>/dev/null && bad "new connection after ssh_open emptied" || ok "new connections refused after the port is removed"
wait %2 2>/dev/null; sleep 5
grep -q still-here $S/sshkeys/held.out && ok "the open session kept working" || bad "open session cut: $(cat $S/sshkeys/held.out)"
echo "ssh/firewall: $pass ok, $fail failed"
[ "$fail" = 0 ]
