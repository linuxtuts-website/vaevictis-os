"""Checks of the apps' own logic against crafted files (no window is opened).

The functions are taken from the real files with ast and run with small stand-ins for Qt/Tk, so only Python, PyMuPDF,
Pillow and mutagen are needed:   python3 -I tests/apps_logic.py build
"""
import ast, math, os, shutil, struct, subprocess, sys, tempfile, types
from datetime import timedelta
from pathlib import Path

B = sys.argv[1]
n = 0
def check(cond, msg):
    global n
    if not cond:
        print("FAIL:", msg); sys.exit(1)
    n += 1

def funcs(path, names, ns):
    """Compile the named functions (top level or methods) of a file into namespace ns."""
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names and node.name not in found:
            found[node.name] = node
    for name in names:
        mod = ast.Module(body=[found[name]], type_ignores=[])
        exec(compile(mod, path, "exec"), ns)
    return ns

def const(path, name):
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return eval(compile(ast.Expression(node.value), path, "eval"))
    raise KeyError(name)

T = tempfile.mkdtemp()

# ---------------------------------------------------------------- Aurora: durations read from files
import mutagen
A = os.path.join(B, "aurora")
ns = funcs(A, ["fmt_time", "_get_meta"], {"math": math, "timedelta": timedelta, "Path": Path, "os": os,
                                          "subprocess": subprocess, "mutagen": mutagen,
                                          "MAX_DURATION": 315360000})
fmt, meta = ns["fmt_time"], ns["_get_meta"]
for bad in (float("inf"), float("-inf"), float("nan"), 1e15, -5, 0, None, "x"):
    check(fmt(None, bad) == "0:00", f"fmt_time({bad!r})")
check(fmt(None, 75) == "1:15" and fmt(None, 3599.9) == "59:59", "fmt_time normal values")
# a FLAC whose header says 2^36-1 samples at 1 sample per second: about 2000 years
wav = os.path.join(T, "long.flac")
bits = (1 << 44) | (0 << 41) | (15 << 36) | ((1 << 36) - 1)          # rate 1 Hz, 1 channel, 16 bit, total samples
info = struct.pack(">HH", 4096, 4096) + b"\x00" * 6 + struct.pack(">Q", bits) + b"\x00" * 16
with open(wav, "wb") as f:
    f.write(b"fLaC" + bytes([0x80]) + len(info).to_bytes(3, "big") + info + b"\xff\xf8" + b"\x00" * 64)
check(mutagen.File(wav).info.length > 1e9, "the crafted FLAC really declares a huge length")
check(meta(None, wav)["duration"] == 0, f"crafted FLAC duration -> {meta(None, wav)['duration']}")
# what mutagen or ffprobe could return: infinite, not a number, negative
class Fake:
    def __init__(self, length): self.info = types.SimpleNamespace(length=length); self.length = length
    def get(self, k, d): return d
for v in (float("inf"), float("nan"), -3.0, 1e12):
    ns["mutagen"] = types.SimpleNamespace(File=lambda p, easy=True, v=v: Fake(v))
    ns["subprocess"] = types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(stdout="inf"))
    check(meta(None, wav)["duration"] == 0, f"duration {v!r} kept")
ns["mutagen"] = types.SimpleNamespace(File=lambda p, easy=True: Fake(245.5))
check(meta(None, wav)["duration"] == 245.5, "a normal duration is kept")

# ---------------------------------------------------------------- VaeVictis PDF: writes never follow a link
import fitz
P = os.path.join(B, "vv-pdf.py")
ns = funcs(P, ["_save_new", "_effective_zoom"], {"os": os, "tempfile": tempfile, "max": max, "min": min,
                                                 "PAD": const(P, "PAD"), "BASE_SCALE": const(P, "BASE_SCALE")})
save_new = ns["_save_new"]
victim = os.path.join(T, "budget.pdf"); open(victim, "wb").write(b"precious")
link = os.path.join(T, "modulo_2.pdf"); os.symlink(victim, link)
dangling = os.path.join(T, "modulo_3.pdf"); os.symlink(os.path.join(T, "nowhere.pdf"), dangling)
doc = fitz.open(); doc.new_page()
for target in (link, dangling):
    save_new(None, target, lambda tmp: doc.save(tmp))
    check(not os.path.islink(target) and open(target, "rb").read(4) == b"%PDF", f"{target}: link replaced by the file")
check(open(victim, "rb").read() == b"precious" and not os.path.exists(os.path.join(T, "nowhere.pdf")),
      "the link targets are untouched")
check(not [f for f in os.listdir(T) if f.startswith(".vvpdf_")], "no temporary file left")
# a page 0 points wide or high must not crash the zoom
class VP:
    def width(self): return 800
    def height(self): return 600
for fit in ("width", "page", None):
    me = types.SimpleNamespace(fit=fit, zoom=1.0, scroll=types.SimpleNamespace(viewport=lambda: VP()))
    for rect in (fitz.Rect(0, 0, 0, 792), fitz.Rect(0, 0, 612, 0)):
        z = ns["_effective_zoom"](me, types.SimpleNamespace(rect=rect))
        check(0.1 <= z <= 8.0, f"zoom for a degenerate page ({fit}) = {z}")
# export of a huge page stays under MAX_PIXELS (same arithmetic as export_png)
MAXP = const(P, "MAX_PIXELS")
big = fitz.open(); pg = big.new_page(width=14400, height=14400)
r = pg.rect; scale = 200 / 72
px = (max(1.0, r.width) * scale) * (max(1.0, r.height) * scale)
if px > MAXP: scale *= (MAXP / px) ** 0.5
pix = pg.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
check(pix.width * pix.height <= MAXP * 1.01, f"export of a huge page: {pix.width}x{pix.height}")
src = open(P, encoding="utf-8").read()
check("self.lbl_info.setTextFormat(Qt.TextFormat.PlainText)" in src, "status bar label is plain text")
check("d2, pw2 = self._authenticated_doc(name)" in src and "self.password = pw2" in src, "merge asks about protection")
check("os.path.lexists(t)" in src, "split checks links that point nowhere")

# ---------------------------------------------------------------- LinPaint+: open and save
from PIL import Image
L = os.path.join(B, "linpaint.py")
shown = []
mb = types.SimpleNamespace(showerror=lambda *a: shown.append(a), showwarning=lambda *a: shown.append(a))
ns = funcs(L, ["write_file", "load_file"], {"os": os, "tempfile": tempfile, "shutil": shutil, "Image": Image,
                                            "messagebox": mb, "APP_NAME": "LinPaint+", "MAX_SIDE": const(L, "MAX_SIDE")})
class Me:
    def __init__(self): self.img = Image.new("RGB", (40, 30), "red"); self.undo_stack = []; self.redo_stack = []; self.filename = None; self.modified = True; self.status = types.SimpleNamespace(config=lambda **k: None)
    def refresh(self): pass
    def update_title(self): pass
me = Me()
pic = os.path.join(T, "important.png"); Image.new("RGB", (5, 5), "blue").save(pic)
plink = os.path.join(T, "download.png"); os.symlink(pic, plink)
check(ns["write_file"](me, plink) is True and not os.path.islink(plink), "save replaces the link with the file")
with Image.open(pic) as im: check(im.size == (5, 5), "the link target is untouched")
for ext in (".jpg", ".png", ".bmp"):
    out = os.path.join(T, "out" + ext)
    check(ns["write_file"](me, out) and Image.open(out).size == (40, 30), f"save as {ext}")
huge = os.path.join(T, "huge.png"); Image.new("1", (9000, 10)).save(huge)
me2 = Me(); shown.clear()
ns["load_file"](me2, huge)
check(me2.img.size == (40, 30) and shown and "too large" in str(shown[-1]), "an image wider than MAX_SIDE is refused")
ok_img = os.path.join(T, "ok.png"); Image.new("RGB", (100, 80)).save(ok_img)
ns["load_file"](me2, ok_img)
check(me2.img.size == (100, 80), "a normal image opens")
check("if code == 1:" in open(L, encoding="utf-8").read(), "cancelling the screenshot does not ask twice")

shutil.rmtree(T)
print(f"apps logic: {n} checks passed")
