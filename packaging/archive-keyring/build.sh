#!/bin/bash
# Builds the LAST vaevictis-archive-keyring .deb: the VaeVictis APT repository is closed, and this version only removes
# what the earlier ones installed (key, source entry, pin). The earlier version (2026.10.13, with the key) is in git history.
# Run it from the repository root:   packaging/archive-keyring/build.sh
# Output: dist/vaevictis-archive-keyring_VERSION_all.deb and its .sha256
set -euo pipefail
export LC_ALL=C

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
out="$root/dist"

for s in preinst postinst postrm; do sh -n "$here/$s"; done
version=$(sed -n 's/^Version: //p' "$here/control")
epoch=${SOURCE_DATE_EPOCH:-$(git -C "$root" log -1 --format=%ct 2>/dev/null || date +%s)}
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
chmod 755 "$stage"

install -d -m 755 "$stage/DEBIAN" "$stage/usr/share/doc/vaevictis-archive-keyring"
install -m 644 "$here/copyright" "$stage/usr/share/doc/vaevictis-archive-keyring/copyright"
gzip -9n -c "$here/changelog" > "$stage/usr/share/doc/vaevictis-archive-keyring/changelog.gz"
chmod 644 "$stage/usr/share/doc/vaevictis-archive-keyring/changelog.gz"
for s in preinst postinst postrm; do install -m 755 "$here/$s" "$stage/DEBIAN/$s"; done
( cd "$stage" && find usr -type f -print0 | sort -z | xargs -0 md5sum ) > "$stage/DEBIAN/md5sums"
chmod 644 "$stage/DEBIAN/md5sums"
size_kb=$(find "$stage/usr" -type f -printf '%s\n' | awk '{s += $1} END {print int((s + 1023) / 1024)}')
{ cat "$here/control"; echo "Installed-Size: $size_kb"; } > "$stage/DEBIAN/control"

find "$stage" -exec touch -h -d "@$epoch" {} +
mkdir -p "$out"
deb="$out/vaevictis-archive-keyring_${version}_all.deb"
dpkg-deb --root-owner-group -Zxz -b "$stage" "$deb" >/dev/null
( cd "$out" && sha256sum "$(basename "$deb")" > "$(basename "$deb").sha256" )
echo "Built: $deb"
cat "$deb.sha256"
