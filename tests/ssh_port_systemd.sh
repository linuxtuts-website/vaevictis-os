#!/bin/bash
# tests/ssh_port_systemd.sh DEBIAN13_ROOT  (as root; use a THROWAWAY Debian 13 root with openssh-server and nftables:
# the 1.3 firewall, the two SSH port drop-ins and an SSH host key are written into it)
# Boots the root's own systemd in new namespaces (pid, mount, network, cgroup) and checks that the SSH port is in the set
# ssh_open exactly while ssh.service runs: after boot, after restarting nftables and ssh together, after reloading or
# restarting nftables, while ssh restarts, after ssh stops and starts again. (1.3)
set -u
D=$(realpath "${1:?usage: ssh_port_systemd.sh DEBIAN13_ROOT}")
HERE=$(cd "$(dirname "$0")" && pwd)
S=$(mktemp -d)
[ -x "$D/usr/lib/systemd/systemd" ] && [ -x "$D/usr/sbin/sshd" ] && [ -x "$D/usr/sbin/nft" ] || { echo "no systemd, sshd or nft in $D" >&2; exit 1; }
mkdir -p "$S/fake/etc/systemd/system" "$S/fake/etc/ssh"; echo 13 > "$S/fake/etc/debian_version"
( cd "$HERE/../build" && VV_CHROOT="$S/fake" VV_SKIP_CHROOT=1 ./vv-harden >/dev/null )
cp "$S/fake/etc/nftables.conf" "$D/etc/nftables.conf"
for d in ssh.service.d/10-vaevictis-firewall.conf nftables.service.d/10-vaevictis-ssh.conf; do
    install -d "$D/etc/systemd/system/${d%/*}"; cp "$S/fake/etc/systemd/system/$d" "$D/etc/systemd/system/$d"
done
install -d "$D/etc/ssh/sshd_config.d"; cp "$S/fake/etc/ssh/sshd_config.d/10-vaevictis.conf" "$D/etc/ssh/sshd_config.d/"
chroot "$D" sh -c '[ -f /etc/ssh/ssh_host_ed25519_key ] || ssh-keygen -q -t ed25519 -N "" -f /etc/ssh/ssh_host_ed25519_key'
# the test restarts the services more often than systemd normally allows
for u in nftables ssh; do printf '[Unit]\nStartLimitIntervalSec=0\n' > "$D/etc/systemd/system/$u.service.d/99-test-no-start-limit.conf"; done
printf '[Unit]\nDescription=VaeVictis SSH port test\nWants=nftables.service ssh.service\n' > "$D/etc/systemd/system/vvtest.target"
ln -sfn /etc/systemd/system/vvtest.target "$D/etc/systemd/system/default.target"

setsid unshare --pid --fork --mount --net --uts --ipc --cgroup --propagation private bash -c "
  mount -t proc proc '$D/proc'; mount -t sysfs sysfs '$D/sys'; mount -t cgroup2 cgroup2 '$D/sys/fs/cgroup'
  mount -t tmpfs tmpfs '$D/run'; mount -t tmpfs tmpfs '$D/tmp'; mount --rbind /dev '$D/dev'
  exec chroot '$D' env container=vvtest /usr/lib/systemd/systemd --system" > "$S/boot.log" 2>&1 &
P=""
for _ in $(seq 1 60); do
    P=$(pgrep -f "^/usr/lib/systemd/systemd --system$" | head -1)
    [ -n "$P" ] && case $(nsenter -t "$P" -m -p -n -r -w systemctl is-system-running 2>/dev/null) in running|degraded) break ;; esac
    timeout 1 tail -f /dev/null
done
[ -n "$P" ] || { echo "systemd did not start"; cat "$S/boot.log"; exit 1; }
trap 'kill -9 "$P" 2>/dev/null; rm -rf "$S"' EXIT
sc() { nsenter -t "$P" -m -p -n -r -w /usr/bin/env PATH=/usr/sbin:/usr/bin:/sbin:/bin "$@"; }
pass=0; fail=0
ok()  { echo "OK   $*"; pass=$((pass+1)); }
bad() { echo "FAIL $*"; fail=$((fail+1)); }
has() { sc nft list set inet vv_filter ssh_open 2>/dev/null | grep -q 'elements = { 2299 }'; }
settle() { for _ in $(seq 1 50); do [ -z "$(sc systemctl list-jobs --no-legend 2>/dev/null)" ] && return 0; timeout 0.2 tail -f /dev/null; done; }
sc systemctl show -p After ssh.service | grep -q nftables.service && ok "ssh.service is ordered after nftables.service" || bad "ssh.service not after nftables"
has && ok "after boot: port in ssh_open" || bad "after boot: port not in ssh_open"
n=0; for _ in $(seq 1 10); do sc systemctl restart nftables.service ssh.service; settle; has || n=$((n+1)); done
[ $n = 0 ] && ok "restart nftables and ssh together (10x): port always there" || bad "restart nftables and ssh together: port missing $n/10"
n=0; for _ in $(seq 1 10); do sc systemctl reload nftables.service; has || n=$((n+1)); done
[ $n = 0 ] && ok "reload nftables (10x): port kept" || bad "reload nftables: port missing $n/10"
n=0; for _ in $(seq 1 10); do sc systemctl restart nftables.service; has || n=$((n+1)); done
[ $n = 0 ] && ok "restart nftables alone (10x): port put back" || bad "restart nftables alone: port missing $n/10"
n=0; for _ in $(seq 1 30); do sc systemctl restart --no-block ssh.service; sc systemctl reload nftables.service; settle
      [ "$(sc systemctl show -P ActiveState ssh.service)" = active ] && { has || n=$((n+1)); }; done
[ $n = 0 ] && ok "reload nftables while ssh restarts (30x): port there whenever ssh runs" || bad "reload nftables while ssh restarts: port missing $n/30"
sc systemctl stop ssh.service; has && bad "ssh stopped: port still open" || ok "ssh stopped: port removed"
sc systemctl reload nftables.service; has && bad "ssh stopped, nftables reloaded: port open" || ok "ssh stopped, nftables reloaded: port stays closed"
sc systemctl restart nftables.service; has && bad "ssh stopped, nftables restarted: port open" || ok "ssh stopped, nftables restarted: port stays closed"
sc systemctl start ssh.service; has && ok "ssh started again: port open" || bad "ssh started again: port missing"
echo "ssh port / systemd: $pass ok, $fail failed"
[ $fail = 0 ]
