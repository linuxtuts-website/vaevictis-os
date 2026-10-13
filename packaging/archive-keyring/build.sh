#!/bin/bash
# Builds the vaevictis-archive-keyring .deb from the files in this folder.
# Run it from the repository root:   packaging/archive-keyring/build.sh
# Output: dist/vaevictis-archive-keyring_VERSION_all.deb and its .sha256
set -euo pipefail
export LC_ALL=C

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
out="$root/dist"
EXPECTED_FPR="0A41158C1DD6718D3D3FFED068486B39B2A99993"

fpr=$(gpg --show-keys --with-colons "$here/vaevictis-archive-keyring.asc" 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}')
[ "$fpr" = "$EXPECTED_FPR" ] || { echo "the key in $here is not the archive key $EXPECTED_FPR: stop and check" >&2; exit 1; }

version=$(sed -n 's/^Version: //p' "$here/control")
epoch=${SOURCE_DATE_EPOCH:-$(git -C "$root" log -1 --format=%ct 2>/dev/null || date +%s)}
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
chmod 755 "$stage"

install -d -m 755 "$stage/DEBIAN" "$stage/usr/share/keyrings" "$stage/etc/apt/sources.list.d" \
                  "$stage/etc/apt/preferences.d" "$stage/usr/share/doc/vaevictis-archive-keyring"
gpg --dearmor < "$here/vaevictis-archive-keyring.asc" > "$stage/usr/share/keyrings/vaevictis-archive-keyring.gpg"
chmod 644 "$stage/usr/share/keyrings/vaevictis-archive-keyring.gpg"
install -m 644 "$here/vaevictis.sources" "$stage/etc/apt/sources.list.d/vaevictis.sources"
install -m 644 "$here/vaevictis.pref"    "$stage/etc/apt/preferences.d/vaevictis"
install -m 644 "$here/copyright"         "$stage/usr/share/doc/vaevictis-archive-keyring/copyright"
gzip -9n -c "$here/changelog" > "$stage/usr/share/doc/vaevictis-archive-keyring/changelog.gz"
chmod 644 "$stage/usr/share/doc/vaevictis-archive-keyring/changelog.gz"
printf '%s\n' /etc/apt/sources.list.d/vaevictis.sources /etc/apt/preferences.d/vaevictis > "$stage/DEBIAN/conffiles"
chmod 644 "$stage/DEBIAN/conffiles"
( cd "$stage" && find usr -type f -print0 | sort -z | xargs -0 md5sum ) > "$stage/DEBIAN/md5sums"
chmod 644 "$stage/DEBIAN/md5sums"
size_kb=$(find "$stage/usr" "$stage/etc" -type f -printf '%s\n' | awk '{s += $1} END {print int((s + 1023) / 1024)}')
{ cat "$here/control"; echo "Installed-Size: $size_kb"; } > "$stage/DEBIAN/control"

find "$stage" -exec touch -h -d "@$epoch" {} +
mkdir -p "$out"
deb="$out/vaevictis-archive-keyring_${version}_all.deb"
dpkg-deb --root-owner-group -Zxz -b "$stage" "$deb" >/dev/null
( cd "$out" && sha256sum "$(basename "$deb")" > "$(basename "$deb").sha256" )
echo "Built: $deb"
cat "$deb.sha256"
