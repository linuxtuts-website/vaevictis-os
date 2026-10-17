#!/bin/bash
# Builds the vaevictis-tools .deb from the files in this repository.
# Run it from the repository root:   packaging/tools/build.sh
# Output: dist/vaevictis-tools_VERSION_all.deb and its .sha256
# The tools are shipped as inert files in /usr/lib/vaevictis-tools; the postinst puts them in place of the copies the
# 1.1 image installed, only where those copies are exactly what VaeVictis shipped (see postinst).
set -euo pipefail
export LC_ALL=C   # the same order of files everywhere

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
out="$root/dist"
files=(vv-sandbox vv-vpn-helper vv-vpn org.vaevictis.vpn.policy v-snap vv-panic vv-panic-action)

for f in "${files[@]}"; do [ -f "$root/build/$f" ] || { echo "missing: build/$f" >&2; exit 1; }; done
bash -n "$root/build/vv-sandbox" && bash -n "$root/build/v-snap" && sh -n "$root/build/vv-panic-action"
python3 -c 'import ast, sys; [ast.parse(open(p, encoding="utf-8").read(), p) for p in sys.argv[1:]]' \
    "$root/build/vv-vpn-helper" "$root/build/vv-vpn" "$root/build/vv-panic"
sh -n "$here/postinst" && sh -n "$here/postrm"
# every payload file must be listed in the postinst
for f in "${files[@]}"; do grep -q " $f " "$here/postinst" || { echo "postinst does not list $f" >&2; exit 1; }; done

version=$(sed -n 's/^Version: //p' "$here/control")
epoch=${SOURCE_DATE_EPOCH:-$(git -C "$root" log -1 --format=%ct 2>/dev/null || date +%s)}
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
chmod 755 "$stage"

install -d -m 755 "$stage/DEBIAN" "$stage/usr/lib/vaevictis-tools" "$stage/usr/share/doc/vaevictis-tools"
for f in "${files[@]}"; do install -m 644 "$root/build/$f" "$stage/usr/lib/vaevictis-tools/$f"; done
install -m 644 "$here/copyright" "$stage/usr/share/doc/vaevictis-tools/copyright"
gzip -9n -c "$here/changelog" > "$stage/usr/share/doc/vaevictis-tools/changelog.gz"
chmod 644 "$stage/usr/share/doc/vaevictis-tools/changelog.gz"
install -m 755 "$here/postinst" "$stage/DEBIAN/postinst"
install -m 755 "$here/postrm"   "$stage/DEBIAN/postrm"
( cd "$stage" && find usr -type f -print0 | sort -z | xargs -0 md5sum ) > "$stage/DEBIAN/md5sums"
chmod 644 "$stage/DEBIAN/md5sums"
size_kb=$(find "$stage/usr" -type f -printf '%s\n' | awk '{s += $1} END {print int((s + 1023) / 1024)}')
{ cat "$here/control"; echo "Installed-Size: $size_kb"; } > "$stage/DEBIAN/control"

find "$stage" -exec touch -h -d "@$epoch" {} +
mkdir -p "$out"
deb="$out/vaevictis-tools_${version}_all.deb"
dpkg-deb --root-owner-group -Zxz -b "$stage" "$deb" >/dev/null
( cd "$out" && sha256sum "$(basename "$deb")" > "$(basename "$deb").sha256" )
echo "Built: $deb"
cat "$deb.sha256"
