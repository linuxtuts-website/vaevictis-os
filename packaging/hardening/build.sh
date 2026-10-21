#!/bin/bash
# Builds the vaevictis-hardening .deb. Run it from the repository root:   packaging/hardening/build.sh
# Output: dist/vaevictis-hardening_VERSION_all.deb and its .sha256
# The files are made by build/vv-harden and build/vv-secure themselves, in their test mode (into a temporary folder, no
# root needed), so each setting is written in one place only. The postinst puts them in place (see postinst).
set -euo pipefail
export LC_ALL=C   # the same order of files everywhere

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
out="$root/dist"
version=$(sed -n 's/^Version: //p' "$here/control")
epoch=${SOURCE_DATE_EPOCH:-$(git -C "$root" log -1 --format=%ct 2>/dev/null || date +%s)}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
chmod 755 "$work"

fake="$work/root"
mkdir -p "$fake/etc/systemd/system" "$fake/etc/ssh" "$fake/etc/sysctl.d"
echo 13 > "$fake/etc/debian_version"
( cd "$root/build" && VV_CHROOT="$fake" VV_SKIP_CHROOT=1 VV_SSH_PORT=2299 VV_IPV6=0 ./vv-harden >/dev/null \
                   && VV_CHROOT="$fake" VV_SKIP_CHROOT=1 ./vv-secure >/dev/null ) \
    || { echo "vv-harden or vv-secure failed in test mode" >&2; exit 1; }

# NAME-in-the-payload:FILE-written-by-the-scripts
files=(sshd-10-vaevictis.conf:etc/ssh/sshd_config.d/10-vaevictis.conf
       nftables.conf:etc/nftables.conf
       10-vaevictis-firewall.conf:etc/systemd/system/ssh.service.d/10-vaevictis-firewall.conf
       10-vaevictis-ssh.conf:etc/systemd/system/nftables.service.d/10-vaevictis-ssh.conf
       99-vaevictis-stealth.conf:etc/sysctl.d/99-vaevictis-stealth.conf
       policies.json:etc/firefox/policies/policies.json)
for e in "${files[@]}"; do [ -s "$fake/${e#*:}" ] || { echo "not written by the scripts: /${e#*:}" >&2; exit 1; }; done
# the files must be the 1.3 ones (the postinst only knows how to replace the 1.1/1.2 versions with these)
grep -qx 'PubkeyAcceptedAlgorithms ssh-ed25519,sk-ssh-ed25519@openssh.com' "$fake/etc/ssh/sshd_config.d/10-vaevictis.conf"
grep -qx 'Subsystem sftp /bin/false' "$fake/etc/ssh/sshd_config.d/10-vaevictis.conf"
grep -q 'set ssh_open' "$fake/etc/nftables.conf"
grep -qx 'net.ipv4.conf.\*.rp_filter = 1' "$fake/etc/sysctl.d/99-vaevictis-stealth.conf"
python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$fake/etc/firefox/policies/policies.json"
if [ "$(id -u)" -eq 0 ] && command -v nft >/dev/null 2>&1; then nft -c -f "$fake/etc/nftables.conf"; fi
sh -n "$here/postinst" && sh -n "$here/postrm"
for e in "${files[@]}"; do grep -q "${e%%:*}" "$here/postinst" || { echo "postinst does not use ${e%%:*}" >&2; exit 1; }; done

stage="$work/stage"
install -d -m 755 "$stage/DEBIAN" "$stage/usr/lib/vaevictis-hardening" "$stage/usr/share/doc/vaevictis-hardening"
for e in "${files[@]}"; do install -m 644 "$fake/${e#*:}" "$stage/usr/lib/vaevictis-hardening/${e%%:*}"; done
install -m 644 "$here/copyright" "$stage/usr/share/doc/vaevictis-hardening/copyright"
gzip -9n -c "$here/changelog" > "$stage/usr/share/doc/vaevictis-hardening/changelog.gz"
chmod 644 "$stage/usr/share/doc/vaevictis-hardening/changelog.gz"
install -m 755 "$here/postinst" "$stage/DEBIAN/postinst"
install -m 755 "$here/postrm"   "$stage/DEBIAN/postrm"
( cd "$stage" && find usr -type f -print0 | sort -z | xargs -0 md5sum ) > "$stage/DEBIAN/md5sums"
chmod 644 "$stage/DEBIAN/md5sums"
size_kb=$(find "$stage/usr" -type f -printf '%s\n' | awk '{s += $1} END {print int((s + 1023) / 1024)}')
{ cat "$here/control"; echo "Installed-Size: $size_kb"; } > "$stage/DEBIAN/control"

find "$stage" -exec touch -h -d "@$epoch" {} +
mkdir -p "$out"
deb="$out/vaevictis-hardening_${version}_all.deb"
dpkg-deb --root-owner-group -Zxz -b "$stage" "$deb" >/dev/null
( cd "$out" && sha256sum "$(basename "$deb")" > "$(basename "$deb").sha256" )
echo "Built: $deb"
cat "$deb.sha256"
