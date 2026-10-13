#!/usr/bin/env python3
"""make-wallpaper.py LOGO FONT OUTFILE : the VaeVictis desktop wallpaper ("dots"), in the style of the boot screens:
near-black, the red logo and the name on the left, a violet halftone (like the dots inside the logo) rising towards the
bottom-right corner, faint isometric lines (like the faces of the logo). 3840x2160, drawn with Pillow only.

  LOGO     build/boot/vaevictis-logo.png
  FONT     IBM Plex Mono Light (package fonts-ibm-plex)
  OUTFILE  .jpg (or .png)
"""
import math
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

W, H = 3840, 2160
BG = (10, 10, 11)
ACCENT = (0x7a, 0x3c, 0xf0)
TEXT = (222, 222, 226)
SMALL = 8          # smooth layers are computed at 1/8 size, then enlarged


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def radial(cx, cy, rx, ry, power, peak):
    """a soft ellipse of light: alpha mask (L), 255*peak at the centre, 0 outside"""
    w, h = W // SMALL, H // SMALL
    m = Image.new("L", (w, h))
    px = m.load()
    for j in range(h):
        dy = ((j + 0.5) * SMALL - cy) / ry
        for i in range(w):
            dx = ((i + 0.5) * SMALL - cx) / rx
            v = clamp(1 - math.sqrt(dx * dx + dy * dy))
            px[i, j] = round(255 * peak * v ** power)
    return m.resize((W, H), Image.BICUBIC)


def iso_lines(step, peak, fade):
    """faint lines at 30 degrees both ways and vertical ones, faded by the mask 'fade'"""
    lines = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(lines)
    run = H / math.tan(math.radians(30))
    span = W + int(run) + step
    for x0 in range(-span, span, step):
        d.line([(x0, 0), (x0 + run, H)], fill=255, width=2)
        d.line([(x0, H), (x0 + run, 0)], fill=255, width=2)
    for x0 in range(0, W, step * 2):
        d.line([(x0, 0), (x0, H)], fill=255, width=2)
    lines = lines.point(lambda v: round(v * peak))
    return ImageChops.multiply(lines, fade)


def halftone(cell, peak):
    """violet dots on a square grid, bigger towards the bottom-right corner, with a slow wave"""
    big = Image.new("L", (W * 2, H * 2), 0)
    d = ImageDraw.Draw(big)
    for gy in range(cell // 2, H, cell):
        for gx in range(cell // 2, W, cell):
            t = (gx / W * 0.62 + gy / H * 0.55) - 0.55 + 0.05 * math.sin(gx / W * 6.0)
            v = clamp(t * 1.7, 0, 0.9) ** 1.5
            if v <= 0.02:
                continue
            r = v * cell * 0.42 * 2
            d.ellipse((gx * 2 - r, gy * 2 - r, gx * 2 + r, gy * 2 + r), fill=255)
    return big.resize((W, H), Image.LANCZOS).point(lambda v: round(v * peak))


def spaced_text(img, text, cx, top, font, tracking):
    d = ImageDraw.Draw(img)
    widths = [d.textlength(c, font=font) for c in text]
    x = cx - (sum(widths) + tracking * (len(text) - 1)) / 2
    for c, w in zip(text, widths):
        d.text((x, top), c, font=font, fill=TEXT)
        x += w + tracking


def main(logo_path, font_path, out):
    img = Image.new("RGB", (W, H), BG)
    violet = Image.new("RGB", (W, H), ACCENT)
    white = Image.new("RGB", (W, H), (255, 255, 255))
    img = Image.composite(violet, img, radial(W * 0.92, H * 1.05, 2200, 1500, 2, 0.35))
    img = Image.composite(white, img, iso_lines(160, 0.035, radial(W * 0.3, H * 0.45, 2000, 1400, 1.5, 1.0)))
    img = Image.composite(violet, img, halftone(40, 0.62))
    # a little noise, so the dark gradient does not show bands on 8-bit screens
    noise = Image.effect_noise((W, H), 1.0)
    img = ImageChops.add(img, Image.merge("RGB", [noise] * 3), scale=1.0, offset=-128)

    src = Image.open(logo_path).convert("RGBA")
    src = src.crop(src.getbbox())
    lh = 320
    lg = src.resize((round(src.width * lh / src.height), lh), Image.LANCZOS) if src.height > lh else src
    lx, ly = int(W * 0.24 - lg.width / 2), int(H * 0.40 - lg.height / 2)
    img = img.convert("RGBA")
    img.alpha_composite(lg, (lx, ly))
    img = img.convert("RGB")
    spaced_text(img, "VAEVICTIS OS", W * 0.24, ly + lg.height + 60, ImageFont.truetype(font_path, 56), 22)

    if out.lower().endswith((".jpg", ".jpeg")):
        img.save(out, quality=92, subsampling=0, optimize=True)
    else:
        img.save(out, optimize=True)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
