#!/bin/bash
# Builds the vaevictis-desktop .deb. Run it from the repository root:   packaging/desktop/build.sh
# Output: dist/vaevictis-desktop_VERSION_all.deb and its .sha256
# Needs on the machine that builds it: python3-pil, grub-common (grub-mkfont), fonts-ibm-plex (a VaeVictis system has them).
# Everything comes from the same files as the image: build/vv-look (icon theme, defaults, run in its test mode into a
# temporary folder) and build/boot (the boot menu: theme.txt, make-images.py, make-grub-fonts.sh).
set -euo pipefail
export LC_ALL=C

here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
out="$root/dist"
version=$(sed -n 's/^Version: //p' "$here/control")
epoch=${SOURCE_DATE_EPOCH:-$(git -C "$root" log -1 --format=%ct 2>/dev/null || date +%s)}
FONTS=${VV_FONTS:-/usr/share/fonts/truetype/ibm-plex}
for t in grub-mkfont python3 dpkg-deb; do command -v $t >/dev/null || { echo "missing: $t" >&2; exit 1; }; done
python3 -c 'import PIL' 2>/dev/null || { echo "missing: python3-pil" >&2; exit 1; }
[ -f "$FONTS/IBMPlexMono-Light.ttf" ] || { echo "missing: IBM Plex fonts in $FONTS (package fonts-ibm-plex)" >&2; exit 1; }
sh -n "$here/postinst" && sh -n "$here/postrm"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
chmod 755 "$work"
fake="$work/root"
mkdir -p "$fake/etc"; echo 13 > "$fake/etc/debian_version"
( cd "$root/build" && VV_CHROOT="$fake" VV_SKIP_CHROOT=1 ./vv-look >/dev/null ) || { echo "vv-look failed in test mode" >&2; exit 1; }

stage="$work/stage"
L="$stage/usr/lib/vaevictis-desktop"
install -d -m 755 "$stage/DEBIAN" "$L/grub-theme" "$stage/usr/share/icons" "$stage/usr/share/doc/vaevictis-desktop"
cp -r "$fake/usr/share/icons/VaeVictis-Dark" "$stage/usr/share/icons/"
install -m 644 "$fake/etc/dconf/db/vaevictis.d/20-look-vaevictis" "$L/20-look-vaevictis"
# the boot menu, made as vv-boot-theme makes it for the image
python3 -I "$root/build/boot/make-images.py" "$work/img" >/dev/null
sh "$root/build/boot/make-grub-fonts.sh" "$FONTS" "$work/img/grub" | grep -qx 'VVOK 6' || { echo "making the GRUB fonts failed" >&2; exit 1; }
install -m 644 "$work/img/grub/"*.png "$work/img/grub/"*.pf2 "$L/grub-theme/"
install -m 644 "$root/build/boot/grub-theme.txt" "$L/grub-theme/theme.txt"
# every font the theme names must be one of the fonts made above (by the name stored inside the .pf2 file)
python3 - "$L/grub-theme" <<'PY'
import glob, re, struct, sys
d = sys.argv[1]
names = set()
for f in glob.glob(d + "/*.pf2"):
    b = open(f, "rb").read(); i = 12
    while i < len(b):
        sec, ln = b[i:i + 4], struct.unpack(">I", b[i + 4:i + 8])[0]
        if sec == b"NAME": names.add(b[i + 8:i + 8 + ln].rstrip(b"\0").decode())
        if sec == b"DATA": break
        i += 8 + ln
used = set(re.findall(r'font\s*[:=]\s*"([^"]+)"', open(d + "/theme.txt").read()))
missing = used - names
if missing: sys.exit("theme.txt names fonts that were not made: %s" % ", ".join(sorted(missing)))
PY
find "$stage/usr" -type d -exec chmod 755 {} + ; find "$stage/usr" -type f -exec chmod 644 {} +
install -m 644 "$here/copyright" "$stage/usr/share/doc/vaevictis-desktop/copyright"
gzip -9n -c "$here/changelog" > "$stage/usr/share/doc/vaevictis-desktop/changelog.gz"
chmod 644 "$stage/usr/share/doc/vaevictis-desktop/changelog.gz"
install -m 755 "$here/postinst" "$stage/DEBIAN/postinst"
install -m 755 "$here/postrm"   "$stage/DEBIAN/postrm"
( cd "$stage" && find usr -type f -print0 | sort -z | xargs -0 md5sum ) > "$stage/DEBIAN/md5sums"
chmod 644 "$stage/DEBIAN/md5sums"
size_kb=$(find "$stage/usr" -type f -printf '%s\n' | awk '{s += $1} END {print int((s + 1023) / 1024)}')
{ cat "$here/control"; echo "Installed-Size: $size_kb"; } > "$stage/DEBIAN/control"

find "$stage" -exec touch -h -d "@$epoch" {} +
mkdir -p "$out"
deb="$out/vaevictis-desktop_${version}_all.deb"
dpkg-deb --root-owner-group -Zxz -b "$stage" "$deb" >/dev/null
( cd "$out" && sha256sum "$(basename "$deb")" > "$(basename "$deb").sha256" )
echo "Built: $deb"
cat "$deb.sha256"
