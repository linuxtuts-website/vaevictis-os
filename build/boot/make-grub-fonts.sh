#!/bin/sh
# make-grub-fonts.sh FONTDIR OUTDIR : the IBM Plex fonts of the VaeVictis boot menu, converted for GRUB (grub-mkfont).
# One list for everything that makes the menu: vv-boot-theme (the image) and packaging/desktop/build.sh (the package
# for installed systems). theme.txt refers to them by name: "VV Mono Regular 13" is family "VV Mono", size 13.
set -e
F=${1:?FONTDIR (fonts-ibm-plex: /usr/share/fonts/truetype/ibm-plex)}
G=${2:?OUTDIR}
mkdir -p "$G"
R=0x20-0x7E,0xA0-0xFF,0x2190-0x2193,0x2022-0x2022,0x2026-0x2026,0x2500-0x257F
# (grub-mkfont warns about OpenType features GRUB does not use: harmless, hidden)
grub-mkfont -r $R -n "VV Sans Light"  -s 22 -o "$G/vv-sans-light-22.pf2"  "$F/IBMPlexSans-Light.ttf"   2>/dev/null
grub-mkfont -r $R -n "VV Mono"        -s 17 -o "$G/vv-mono-17.pf2"        "$F/IBMPlexMono-Regular.ttf" 2>/dev/null
grub-mkfont -r $R -n "VV Mono Medium" -s 17 -o "$G/vv-mono-medium-17.pf2" "$F/IBMPlexMono-Medium.ttf"  2>/dev/null
grub-mkfont -r $R -n "VV Mono"        -s 13 -o "$G/vv-mono-13.pf2"        "$F/IBMPlexMono-Regular.ttf" 2>/dev/null
grub-mkfont -r $R -n "VV Mono"        -s 16 -o "$G/vv-mono-16.pf2"        "$F/IBMPlexMono-Regular.ttf" 2>/dev/null
# the countdown (1.3): digits only are needed, ASCII is enough
grub-mkfont -r 0x20-0x7E -n "VV Mono Light" -s 30 -o "$G/vv-mono-light-30.pf2" "$F/IBMPlexMono-Light.ttf" 2>/dev/null
echo "VVOK $(ls "$G"/*.pf2 | wc -l)"
