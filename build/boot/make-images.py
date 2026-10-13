#!/usr/bin/env python3
"""make-images.py OUTDIR : the pictures of the VaeVictis boot screens (style A, minimal), drawn from the logo next to this
file with Pillow. Same input, same output: run it again after changing a colour or a size.

  OUTDIR/grub/      logo.png, select_*.png (the violet box behind the chosen menu entry, in nine pieces)
  OUTDIR/plymouth/  logo.png, field.png (passphrase box), bullet.png, track.png, accent.png
"""
import os
import sys
from PIL import Image, ImageDraw

ACCENT = (0x7a, 0x3c, 0xf0, 255)     # violet chosen for the boot screens
TRACK = (0x26, 0x26, 0x2a, 255)      # empty part of the progress bar
FIELD = (0x14, 0x14, 0x16, 255)      # inside of the passphrase box
HERE = os.path.dirname(os.path.abspath(__file__))


def logo(width):
    src = Image.open(os.path.join(HERE, "vaevictis-logo.png")).convert("RGBA")
    src = src.crop(src.getbbox())
    h = round(src.height * width / src.width)
    return src.resize((width, h), Image.LANCZOS)


def rounded(w, h, r, fill, outline=None, scale=4):
    big = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle((0, 0, w * scale - 1, h * scale - 1), radius=r * scale, fill=fill,
                        outline=outline, width=scale if outline else 0)
    return big.resize((w, h), Image.LANCZOS)


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)


def main(out):
    # GRUB: logo 72 px wide; selection box with 4 px rounded corners, cut in nine pieces (GRUB stretches the middle ones)
    save(logo(72), f"{out}/grub/logo.png")
    r = 4
    box = rounded(3 * r, 3 * r, r, ACCENT)
    pieces = {"nw": (0, 0), "n": (r, 0), "ne": (2 * r, 0), "w": (0, r), "c": (r, r), "e": (2 * r, r),
              "sw": (0, 2 * r), "s": (r, 2 * r), "se": (2 * r, 2 * r)}
    for name, (x, y) in pieces.items():
        save(box.crop((x, y, x + r, y + r)), f"{out}/grub/select_{name}.png")
    # Plymouth: logo 120 px (the script scales it for the passphrase screen), passphrase box, bullet, 1-pixel colours
    save(logo(120), f"{out}/plymouth/logo.png")
    save(rounded(420, 48, 6, FIELD, outline=ACCENT), f"{out}/plymouth/field.png")
    dot = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(dot).ellipse((4, 4, 35, 35), fill=(255, 255, 255, 255))
    save(dot.resize((10, 10), Image.LANCZOS), f"{out}/plymouth/bullet.png")
    save(Image.new("RGBA", (1, 1), TRACK), f"{out}/plymouth/track.png")
    save(Image.new("RGBA", (1, 1), ACCENT), f"{out}/plymouth/accent.png")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
