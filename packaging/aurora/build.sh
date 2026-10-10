#!/bin/bash
# Builds the vaevictis-aurora .deb from the files in this repository.
# Run it from the repository root:   packaging/aurora/build.sh
# Output: dist/vaevictis-aurora_VERSION_all.deb and its .sha256
# The build is repeatable: the same files give the same .deb on the same Debian release
# (file dates are fixed; a different dpkg or xz version can change the compressed bytes).
set -euo pipefail
export LC_ALL=C   # the same order of files everywhere

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
src="${1:-$root/build/aurora}"
out="$root/dist"

[ -f "$src" ] || { echo "Aurora program not found: $src" >&2; exit 1; }
head -n 5 "$src" | grep -q 'Aurora - Ultimate Carbon Dark Edition' || { echo "$src does not look like Aurora" >&2; exit 1; }
python3 -m py_compile "$src" && rm -rf "$(dirname "$src")/__pycache__/aurora"*.pyc 2>/dev/null || true

version=$(sed -n 's/^Version: //p' "$here/control")
epoch=${SOURCE_DATE_EPOCH:-$(git -C "$root" log -1 --format=%ct 2>/dev/null || date +%s)}
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
chmod 755 "$stage"

install -d -m 755 "$stage/DEBIAN" "$stage/usr/bin" "$stage/usr/share/applications" "$stage/usr/share/man/man1" "$stage/usr/share/doc/vaevictis-aurora"
install -m 755 "$src"                 "$stage/usr/bin/aurora"
install -m 644 "$here/aurora.desktop" "$stage/usr/share/applications/aurora.desktop"
install -m 644 "$here/copyright"      "$stage/usr/share/doc/vaevictis-aurora/copyright"
gzip -9n -c "$here/changelog" >        "$stage/usr/share/doc/vaevictis-aurora/changelog.gz"
chmod 644 "$stage/usr/share/doc/vaevictis-aurora/changelog.gz"
gzip -9n -c "$here/aurora.1" > "$stage/usr/share/man/man1/aurora.1.gz"
chmod 644 "$stage/usr/share/man/man1/aurora.1.gz"
install -m 755 "$here/postinst" "$stage/DEBIAN/postinst"
install -m 755 "$here/postrm"   "$stage/DEBIAN/postrm"
( cd "$stage" && find usr -type f -print0 | sort -z | xargs -0 md5sum ) > "$stage/DEBIAN/md5sums"
chmod 644 "$stage/DEBIAN/md5sums"
size_kb=$(find "$stage/usr" -type f -printf '%s\n' | awk '{s += $1} END {print int((s + 1023) / 1024)}')   # same on every file system
{ cat "$here/control"; echo "Installed-Size: $size_kb"; } > "$stage/DEBIAN/control"

find "$stage" -exec touch -h -d "@$epoch" {} +
mkdir -p "$out"
deb="$out/vaevictis-aurora_${version}_all.deb"
dpkg-deb --root-owner-group -Zxz -b "$stage" "$deb" >/dev/null
( cd "$out" && sha256sum "$(basename "$deb")" > "$(basename "$deb").sha256" )
echo "Built: $deb"
cat "$deb.sha256"
