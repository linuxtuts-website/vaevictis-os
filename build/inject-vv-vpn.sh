#!/usr/bin/env bash
# Installs VaeVictis VPN into a chroot (default: your debootstrap chroot).
# Usage: ./inject-vv-vpn.sh [CHROOT_PATH]
set -euo pipefail

CHROOT="${1:-/home/vaevictis/new/chroot}"
SRC="$(cd "$(dirname "$0")" && pwd)"

[ "$(id -u)" -eq 0 ] || exec sudo "$0" "$@"
[ -d "$CHROOT/usr" ] || { echo "Chroot not found: $CHROOT" >&2; exit 1; }
for f in vv-vpn vv-vpn-helper org.vaevictis.vpn.policy vv-vpn.desktop; do
    [ -f "$SRC/$f" ] || { echo "Missing file next to this script: $f" >&2; exit 1; }
done

install -D -m 0755 "$SRC/vv-vpn"                  "$CHROOT/usr/local/bin/vv-vpn"
install -D -m 0755 "$SRC/vv-vpn-helper"           "$CHROOT/usr/local/libexec/vv-vpn-helper"
install -D -m 0644 "$SRC/org.vaevictis.vpn.policy" "$CHROOT/usr/share/polkit-1/actions/org.vaevictis.vpn.policy"
install -D -m 0644 "$SRC/vv-vpn.desktop"          "$CHROOT/usr/share/applications/vv-vpn.desktop"
install -d -m 0755 "$CHROOT/var/lib/vv-vpn"
install -d -m 0700 "$CHROOT/etc/wireguard"

echo "VaeVictis VPN installed in $CHROOT"
echo
echo "Make sure these packages are in the chroot (apt install --no-install-recommends ...):"
echo "  python3-gi gir1.2-gtk-3.0 wireguard-tools iproute2 pkexec polkitd curl openresolv"
