#!/usr/bin/env python3
"""
LinPaint+ - A modern MS Paint-style drawing program for Linux
Version: 2.3 - drawn icons, eraser, persistent colors

Dependencies:
    openSUSE : python3-tk python3-Pillow python3-Pillow-tk python3-gobject
    Debian   : sudo apt install python3-tk python3-pil python3-pil.imagetk python3-gi

Run:
    python3 linpaint.py [image.png]
"""

import argparse
import colorsys
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFont, ImageOps, ImageTk

APP_NAME = "LinPaint+"
APP_VERSION = "2.3"
MAX_UNDO = 30
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".config", "linpaint", "settings.json")

# === DARK THEME ===
PROTON_PRIMARY = "#4f8cff"
PROTON_PRIMARY_DARK = "#3a6fd8"
PROTON_ACCENT_TEXT = "#8ab4ff"
PROTON_DARK_BG = "#15171c"
PROTON_DARK_PANEL = "#1d2027"
PROTON_DARK_ACCENT = "#292d36"
PROTON_HOVER = "#363b47"
PROTON_QUICK_BTN = "#181a20"
PROTON_TEXT_MAIN = "#ffffff"
PROTON_TEXT_MUTED = "#a3a8b5"
PROTON_BORDER = "#3a3f4b"

PALETTE = [
    "#000000", "#4a4a4a", "#880015", "#ed1c24", "#ff7f27",
    "#fff200", "#22b14c", "#00a2e8", "#3f48cc", "#4f8cff",
    "#ffffff", "#c3c3c3", "#b97a57", "#ffaec9", "#ffc90e",
    "#efe4b0", "#b5e61d", "#99d9ea", "#7092be", "#c8d4e7",
]

TOOLS = [
    ("pencil", "Pencil"),
    ("brush", "Brush"),
    ("spray", "Spray"),
    ("eraser", "Eraser"),
    ("fill", "Fill"),
    ("picker", "Picker"),
    ("text", "Text"),
    ("line", "Line"),
    ("rect", "Rectangle"),
    ("ellipse", "Ellipse"),
]

TOOL_HINTS = {
    "pencil": "Pencil: thin 1px freehand line",
    "brush": "Brush: freehand line, uses Thickness",
    "spray": "Spray: airbrush",
    "eraser": "Eraser: paints with the secondary color (white by default, right-click a color to change)",
    "fill": "Fill: click an area to fill it with the primary color",
    "picker": "Picker: click the image to take a color",
    "text": "Text: drag a box, type, Shift+Enter to confirm",
    "line": "Line: drag (Shift = 45 degree angles)",
    "rect": "Rectangle: drag (Shift = square)",
    "ellipse": "Ellipse: drag (Shift = circle)",
}

CURSORS = {
    "pencil": "pencil", "brush": "pencil", "spray": "spraycan", "eraser": "dotbox",
    "fill": "crosshair", "picker": "crosshair", "text": "xterm",
    "line": "crosshair", "rect": "crosshair", "ellipse": "crosshair",
}

FREEHAND = {"pencil", "brush", "spray", "eraser"}
SHAPES = {"line", "rect", "ellipse"}

THICKNESS_PRESETS = [
    (1, "Fine"),
    (3, "Normal"),
    (5, "Thick"),
    (10, "Very Thick"),
]


# ------------------------------------------------------------ SETTINGS
def _load_cfg():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_cfg(data):
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def _valid_color(value, default):
    try:
        ImageColor.getrgb(value)
        return value
    except Exception:
        return default


# ------------------------------------------------------------ ICONS
def make_icon(key, px=34):
    """Draw a tool icon with PIL (no emoji font needed)."""
    S = 4
    img = Image.new("RGBA", (64 * S, 64 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def P(pts):
        return [(x * S, y * S) for x, y in pts]

    def Bx(b):
        return [v * S for v in b]

    W = "#e8e4ff"
    ACC = "#8ab4ff"
    YEL = "#ffd23f"
    PINK = "#ff8fa3"
    GREY = "#9aa5c8"
    DARK = "#2b2b3a"

    if key == "pencil":
        d.polygon(P([(22, 49), (55.5, 15.5), (48.5, 8.5), (15, 42)]), fill=YEL)
        d.polygon(P([(48.5, 8.5), (55.5, 15.5), (59, 12), (52, 5)]), fill=PINK)
        d.polygon(P([(15, 42), (22, 49), (10, 54)]), fill="#f2c7a0")
        d.polygon(P([(10, 54), (11.5, 50.4), (13.6, 52.5)]), fill=DARK)
    elif key == "brush":
        d.line(P([(54, 8), (31, 31)]), fill="#c58b5a", width=6 * S)
        d.line(P([(31, 31), (25, 37)]), fill="#cfd3dc", width=8 * S)
        d.polygon(P([(21, 38), (29, 44), (25, 54), (9, 57), (14, 47)]), fill=ACC)
    elif key == "spray":
        d.rectangle(Bx((24, 24, 44, 58)), fill=GREY)
        d.rectangle(Bx((27, 14, 41, 24)), fill=W)
        d.rectangle(Bx((34, 8, 45, 14)), fill=W)
        for x, y in ((8, 12), (14, 6), (6, 22), (14, 16), (10, 28), (18, 22)):
            d.ellipse(Bx((x - 2, y - 2, x + 2, y + 2)), fill=ACC)
    elif key == "eraser":
        a, b, c, e = (10, 40), (30, 20), (52, 42), (32, 62)
        m1, m2 = (18.8, 48.8), (38.8, 28.8)
        d.polygon(P([a, b, m2, m1]), fill=PINK)
        d.polygon(P([m1, m2, c, e]), fill=W)
        d.line(P([a, b, c, e, a]), fill=GREY, width=2 * S)
    elif key == "fill":
        d.polygon(P([(12, 26), (40, 26), (36, 54), (16, 54)]), fill=GREY)
        d.polygon(P([(14, 36), (38, 36), (36, 54), (16, 54)]), fill=PROTON_PRIMARY)
        d.ellipse(Bx((12, 22, 40, 30)), fill=W)
        d.arc(Bx((14, 10, 38, 42)), 200, 340, fill=W, width=3 * S)
        d.polygon(P([(52, 34), (46, 44), (58, 44)]), fill=ACC)
        d.ellipse(Bx((46, 40, 58, 52)), fill=ACC)
    elif key == "picker":
        d.polygon(P([(41.2, 17.2), (46.8, 22.8), (16.8, 52.8), (11.2, 47.2)]), fill=W)
        d.line(P([(14, 50), (8, 56)]), fill=YEL, width=3 * S)
        d.ellipse(Bx((40, 6, 58, 24)), fill=ACC)
        d.line(P([(38, 14), (52, 28)]), fill=W, width=3 * S)
    elif key == "text":
        d.rectangle(Bx((10, 10, 54, 20)), fill=W)
        d.rectangle(Bx((27, 20, 37, 56)), fill=W)
    elif key == "line":
        d.line(P([(12, 52), (52, 12)]), fill=W, width=5 * S)
        for cx, cy in ((12, 52), (52, 12)):
            d.ellipse(Bx((cx - 5, cy - 5, cx + 5, cy + 5)), fill=ACC)
    elif key == "rect":
        d.rounded_rectangle(Bx((10, 16, 54, 48)), radius=6 * S, outline=W, width=5 * S)
    elif key == "ellipse":
        d.ellipse(Bx((8, 14, 56, 50)), outline=W, width=5 * S)

    return img.resize((px, px), Image.Resampling.LANCZOS)


def load_font(size):
    """Load a readable font with fallback"""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/noto/Roboto-Regular.ttf",
        "/usr/share/fonts/google-noto/NotoSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    try:
        return ImageFont.load_default()
    except TypeError:
        return ImageFont.load_default()


def find_icon():
    """Find app icon"""
    here = os.path.dirname(os.path.abspath(__file__))
    home = os.path.expanduser("~")
    for path in (
        os.path.join(here, "linpaint.png"),
        os.path.join(here, "linpaint.svg"),
        "/usr/share/pixmaps/linpaint.png",
        os.path.join(home, ".local/share/icons/hicolor/256x256/apps/linpaint.png"),
        "/usr/share/icons/hicolor/256x256/apps/linpaint.png",
    ):
        if os.path.exists(path):
            return path
    return None


PORTAL_SCRIPT = r"""
import os, sys, time
from urllib.parse import unquote, urlparse
import gi
from gi.repository import Gio, GLib

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
sender = bus.get_unique_name()[1:].replace(".", "_")

def request(interactive):
    token = "linpaint%d_%d" % (os.getpid(), int(interactive))
    request_path = "/org/freedesktop/portal/desktop/request/%s/%s" % (sender, token)
    result = {}

    def on_response(conn, sender_name, path, iface, signal, params, user_data):
        result["data"] = params.unpack()

    sub = bus.signal_subscribe("org.freedesktop.portal.Desktop", "org.freedesktop.portal.Request",
                               "Response", request_path, None, Gio.DBusSignalFlags.NONE,
                               on_response, None)
    options = {"handle_token": GLib.Variant("s", token),
               "interactive": GLib.Variant("b", interactive)}
    bus.call_sync("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                  "org.freedesktop.portal.Screenshot", "Screenshot",
                  GLib.Variant("(sa{sv})", ("", options)), None, Gio.DBusCallFlags.NONE, -1, None)
    ctx = GLib.MainContext.default()
    deadline = time.time() + 60
    while "data" not in result and time.time() < deadline:
        ctx.iteration(False)
        time.sleep(0.02)
    bus.signal_unsubscribe(sub)
    if "data" not in result:
        sys.exit("timeout")
    return result["data"]

for interactive in (False, True):
    code, res = request(interactive)
    if code == 0 and "uri" in res:
        print(unquote(urlparse(res["uri"]).path))
        sys.exit(0)
sys.exit("cancelled")
"""


def grab_screen():
    """Capture full screen"""
    wayland = (os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
               or bool(os.environ.get("WAYLAND_DISPLAY")))
    tmpdir = tempfile.mkdtemp(prefix="linpaint-")
    path = os.path.join(tmpdir, "shot.png")

    def via_pillow():
        from PIL import ImageGrab
        return ImageGrab.grab().convert("RGB")

    def via_command(cmd):
        def run():
            subprocess.run(cmd, check=True, timeout=20,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return Image.open(path).convert("RGB")
        return run

    def via_portal():
        last = "python3-gi not available"
        for py in dict.fromkeys([sys.executable, "/usr/bin/python3"]):
            if not py or not os.path.exists(py):
                continue
            r = subprocess.run([py, "-c", PORTAL_SCRIPT], capture_output=True, text=True, timeout=90)
            out = r.stdout.strip().splitlines()
            if r.returncode == 0 and out:
                file = out[-1]
                try:
                    return Image.open(file).convert("RGB")
                finally:
                    try:
                        os.remove(file)
                    except OSError:
                        pass
            last = (r.stderr.strip().splitlines() or ["error"])[-1]
            if "cancelled" in last or "timeout" in last:
                break
        raise RuntimeError(last)

    tools = [
        ("gnome-screenshot", ["gnome-screenshot", "-f", path]),
        ("spectacle", ["spectacle", "-b", "-n", "-f", "-o", path]),
        ("grim", ["grim", path]),
        ("maim", ["maim", path]),
        ("scrot", ["scrot", path]),
        ("import", ["import", "-window", "root", path]),
    ]
    methods = []
    if wayland:
        methods.append(("portal", via_portal))
    else:
        methods.append(("Pillow", via_pillow))
    methods += [(name, via_command(cmd)) for name, cmd in tools if shutil.which(name)]
    if wayland:
        methods.append(("Pillow", via_pillow))

    errors = []
    try:
        for name, fn in methods:
            try:
                img = fn()
            except Exception as e:
                errors.append(f"{name}: {e}")
                continue
            if img.getbbox() is None:
                errors.append(f"{name}: empty")
                continue
            return img
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    raise RuntimeError(
        "Cannot capture screen.\n\n"
        "Install: gnome-screenshot or grim (Sway)\n\n"
        "Details:\n" + "\n".join(errors))


class LinPaint:
    def __init__(self, root, filename=None):
        self.root = root
        root.configure(bg=PROTON_DARK_BG)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=PROTON_DARK_PANEL)
        style.configure("TLabel", background=PROTON_DARK_PANEL, foreground=PROTON_TEXT_MAIN)
        style.configure("TButton", background=PROTON_DARK_ACCENT, foreground=PROTON_TEXT_MAIN)
        style.configure("Vertical.TScrollbar", background=PROTON_DARK_PANEL,
                        troughcolor=PROTON_BORDER, arrowcolor=PROTON_TEXT_MAIN)
        style.configure("Horizontal.TScrollbar", background=PROTON_DARK_PANEL,
                        troughcolor=PROTON_BORDER, arrowcolor=PROTON_TEXT_MAIN)

        cfg = _load_cfg()
        tool_keys = [k for k, _ in TOOLS]
        start_tool = cfg.get("tool") if cfg.get("tool") in tool_keys else "pencil"
        try:
            start_size = max(1, min(50, int(cfg.get("size", 3))))
        except (TypeError, ValueError):
            start_size = 3
        start_fill = cfg.get("fill_mode") if cfg.get("fill_mode") in ("outline", "filled", "both") else "outline"

        self.tool = tk.StringVar(value=start_tool)
        self.size = tk.IntVar(value=start_size)
        self.fill_mode = tk.StringVar(value=start_fill)
        self.delay = tk.IntVar(value=0)
        self.fg = _valid_color(cfg.get("fg", PROTON_PRIMARY), PROTON_PRIMARY)
        self.bg = _valid_color(cfg.get("bg", "#ffffff"), "#ffffff")
        recent = cfg.get("recent")
        if isinstance(recent, list) and recent:
            self.recent_colors = [_valid_color(c, "#000000") for c in recent[:6]]
        else:
            self.recent_colors = [PROTON_PRIMARY, "#000000", "#ffffff", "#ed1c24", "#22b14c", "#00a2e8"]

        self.img = Image.new("RGB", (900, 600), "white")
        self.base = None
        self.undo_stack = []
        self.redo_stack = []
        self.filename = None
        self.modified = False
        self.zoom_level = 1.0

        self.start = None
        self.last = None
        self.cur_color = self.fg
        self.other_color = self.bg

        self.active_text_widget = None
        self.text_rect_id = None
        self.text_start_pos = None
        self.text_pil_pos = None
        self.tooltip_window = None
        self.icons = {}

        self.set_window_icon()
        self.build_menu()
        self.build_ui()
        self.bind_keys()

        self.tool.trace_add("write", self.on_tool_change)
        self.size.trace_add("write", self.on_size_change)
        self.on_tool_change()
        self.on_size_change()

        if filename and os.path.exists(filename):
            self.load_file(filename)
        self.refresh()
        self.update_title()
        root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---------------------------------------------------------------- SETTINGS
    def save_settings(self):
        try:
            size = self.size.get()
        except tk.TclError:
            size = 3
        _save_cfg({
            "fg": self.fg, "bg": self.bg, "size": size,
            "tool": self.tool.get(), "fill_mode": self.fill_mode.get(),
            "recent": self.recent_colors[:6],
        })

    def on_tool_change(self, *args):
        self.finalize_text()
        t = self.tool.get()
        self.canvas.config(cursor=CURSORS.get(t, "crosshair"))
        self.status.config(text=TOOL_HINTS.get(t, "Ready"))
        self.save_settings()

    def on_size_change(self, *args):
        try:
            self.thickness_label.config(text=f"{self.size.get()}px")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ MENU
    def build_menu(self):
        menubar = tk.Menu(self.root, bg=PROTON_DARK_BG, fg=PROTON_TEXT_MAIN,
                          activebackground=PROTON_PRIMARY, activeforeground="white")

        m = tk.Menu(menubar, tearoff=0, bg=PROTON_DARK_PANEL, fg=PROTON_TEXT_MAIN)
        m.add_command(label="New...", accelerator="Ctrl+N", command=self.new_image)
        m.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_image)
        m.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        m.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_as)
        m.add_separator()
        m.add_command(label="Export PNG", command=lambda: self.save_format("PNG"))
        m.add_command(label="Export JPEG", command=lambda: self.save_format("JPEG"))
        m.add_separator()
        m.add_command(label="Exit", accelerator="Ctrl+Q", command=self.quit)
        menubar.add_cascade(label="File", menu=m)

        m = tk.Menu(menubar, tearoff=0, bg=PROTON_DARK_PANEL, fg=PROTON_TEXT_MAIN)
        m.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        m.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo)
        m.add_separator()
        m.add_command(label="Copy", accelerator="Ctrl+C", command=self.copy_to_clipboard)
        m.add_command(label="Paste", accelerator="Ctrl+V", command=self.paste_from_clipboard)
        m.add_separator()
        m.add_command(label="Clear All", command=self.clear_all)
        menubar.add_cascade(label="Edit", menu=m)

        m = tk.Menu(menubar, tearoff=0, bg=PROTON_DARK_PANEL, fg=PROTON_TEXT_MAIN)
        m.add_command(label="Resize Canvas...", command=self.resize_canvas)
        m.add_separator()
        m.add_command(label="Rotate 90° Left", command=lambda: self.transform("rot_l"))
        m.add_command(label="Rotate 90° Right", command=lambda: self.transform("rot_r"))
        m.add_command(label="Flip Horizontal", command=lambda: self.transform("mirror"))
        m.add_command(label="Flip Vertical", command=lambda: self.transform("flip"))
        m.add_separator()
        m.add_command(label="Invert Colors", command=lambda: self.transform("invert"))
        m.add_command(label="Grayscale", command=lambda: self.transform("grayscale"))
        m.add_command(label="Increase Contrast", command=lambda: self.transform("contrast_up"))
        menubar.add_cascade(label="Image", menu=m)

        m = tk.Menu(menubar, tearoff=0, bg=PROTON_DARK_PANEL, fg=PROTON_TEXT_MAIN)
        m.add_command(label="Full Screen", accelerator="Ctrl+Shift+F",
                      command=lambda: self.take_screenshot(area=False))
        m.add_command(label="Select Area...", accelerator="Ctrl+Shift+A",
                      command=lambda: self.take_screenshot(area=True))
        m.add_separator()
        delay_menu = tk.Menu(m, tearoff=0, bg=PROTON_DARK_PANEL, fg=PROTON_TEXT_MAIN)
        for sec in (0, 3, 5, 10):
            delay_menu.add_radiobutton(label="None" if sec == 0 else f"{sec}s",
                                       value=sec, variable=self.delay)
        m.add_cascade(label="Delay", menu=delay_menu)
        menubar.add_cascade(label="Screenshot", menu=m)

        m = tk.Menu(menubar, tearoff=0, bg=PROTON_DARK_PANEL, fg=PROTON_TEXT_MAIN)
        m.add_command(label="Zoom In", accelerator="+", command=self.zoom_in)
        m.add_command(label="Zoom Out", accelerator="-", command=self.zoom_out)
        m.add_command(label="Zoom 100%", accelerator="0", command=self.zoom_reset)
        menubar.add_cascade(label="View", menu=m)

        m = tk.Menu(menubar, tearoff=0, bg=PROTON_DARK_PANEL, fg=PROTON_TEXT_MAIN)
        m.add_command(label="About", command=self.about)
        menubar.add_cascade(label="Help", menu=m)

        self.root.config(menu=menubar)

    # -------------------------------------------------------------------- UI
    def section(self, parent, text):
        tk.Label(parent, text=text, font=("Helvetica", 9, "bold"),
                 fg=PROTON_ACCENT_TEXT, bg=PROTON_DARK_PANEL,
                 anchor="w").pack(anchor="w", pady=(10, 4))

    def build_ui(self):
        # ===== LEFT PANEL =====
        left = tk.Frame(self.root, bg=PROTON_DARK_PANEL, padx=10, pady=10)
        left.pack(side=tk.LEFT, fill=tk.Y)

        header = tk.Frame(left, bg=PROTON_PRIMARY)
        header.pack(fill=tk.X, pady=(0, 8))
        tk.Label(header, text=APP_NAME, bg=PROTON_PRIMARY, fg="white",
                 font=("Helvetica", 13, "bold")).pack(pady=(6, 0))
        tk.Label(header, text=f"v{APP_VERSION}", bg=PROTON_PRIMARY, fg="#dbe7ff",
                 font=("Helvetica", 8)).pack(pady=(0, 6))

        quick = tk.Frame(left, bg=PROTON_DARK_PANEL)
        quick.pack(fill=tk.X, pady=(0, 4))
        for txt, cmd in (("Undo", self.undo), ("Redo", self.redo), ("Clear", self.clear_all)):
            b = tk.Button(quick, text=txt, command=cmd, bg=PROTON_QUICK_BTN,
                          fg=PROTON_TEXT_MAIN, relief=tk.FLAT, bd=0, padx=8, pady=4,
                          font=("Helvetica", 9), cursor="hand2",
                          activebackground=PROTON_DARK_ACCENT, activeforeground="white")
            b.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
            self.add_tooltip(b, txt)

        self.section(left, "TOOLS")
        grid = tk.Frame(left, bg=PROTON_DARK_PANEL)
        grid.pack()
        for i, (key, label) in enumerate(TOOLS):
            self.icons[key] = ImageTk.PhotoImage(make_icon(key, 34))
            btn = tk.Radiobutton(grid, text=label, image=self.icons[key], compound=tk.TOP,
                                 value=key, variable=self.tool, indicatoron=False,
                                 bg=PROTON_DARK_ACCENT, fg=PROTON_TEXT_MAIN,
                                 selectcolor=PROTON_PRIMARY,
                                 activebackground=PROTON_HOVER, activeforeground="white",
                                 relief=tk.FLAT, bd=0, highlightthickness=0,
                                 padx=4, pady=4, width=80,
                                 font=("Helvetica", 8), cursor="hand2")
            btn.grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky="ew")
            self.add_tooltip(btn, TOOL_HINTS[key])

        self.section(left, "THICKNESS")
        self.thickness_scale = tk.Scale(left, from_=1, to=50, orient=tk.HORIZONTAL,
                                        variable=self.size, length=170,
                                        troughcolor=PROTON_BORDER, highlightthickness=0,
                                        sliderlength=16, bg=PROTON_DARK_ACCENT,
                                        fg=PROTON_TEXT_MAIN, bd=0, showvalue=False)
        self.thickness_scale.pack(fill=tk.X)
        self.thickness_label = tk.Label(left, text="3px", font=("Helvetica", 9),
                                        fg=PROTON_TEXT_MUTED, bg=PROTON_DARK_PANEL)
        self.thickness_label.pack()

        preset_frame = tk.Frame(left, bg=PROTON_DARK_PANEL)
        preset_frame.pack(fill=tk.X, pady=(4, 0))
        for width, name in THICKNESS_PRESETS:
            btn = tk.Button(preset_frame, text=str(width), command=lambda w=width: self.size.set(w),
                            bg=PROTON_DARK_ACCENT, fg=PROTON_TEXT_MAIN, relief=tk.FLAT, bd=0,
                            font=("Helvetica", 9), cursor="hand2",
                            activebackground=PROTON_PRIMARY, activeforeground="white")
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2, ipady=2)
            self.add_tooltip(btn, f"{name} ({width}px)")

        self.section(left, "SHAPES")
        shapes = tk.Frame(left, bg=PROTON_DARK_PANEL)
        shapes.pack(fill=tk.X)
        for text, val in (("Outline", "outline"), ("Filled", "filled"), ("Both", "both")):
            btn = tk.Radiobutton(shapes, text=text, value=val, variable=self.fill_mode,
                                 indicatoron=False, bg=PROTON_DARK_ACCENT,
                                 fg=PROTON_TEXT_MAIN, selectcolor=PROTON_PRIMARY,
                                 activebackground=PROTON_HOVER, activeforeground="white",
                                 relief=tk.FLAT, bd=0, highlightthickness=0,
                                 font=("Helvetica", 9), cursor="hand2")
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2, ipady=3)
            self.add_tooltip(btn, f"Shape style: {text}")

        # ===== STATUS BAR (lowest) =====
        self.status = tk.Label(self.root, text="Ready", anchor="w", relief=tk.FLAT,
                               bg=PROTON_DARK_BG, fg=PROTON_TEXT_MUTED,
                               font=("Monospace", 9), padx=10, pady=4)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        # ===== COLOR BAR =====
        bottom = tk.Frame(self.root, bg=PROTON_DARK_PANEL, height=100)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        bottom.pack_propagate(False)

        cp = tk.Frame(bottom, bg=PROTON_DARK_PANEL, padx=12, pady=10)
        cp.pack(side=tk.LEFT, fill=tk.Y)
        self.indicator = tk.Canvas(cp, width=64, height=64, bg=PROTON_DARK_PANEL,
                                   highlightthickness=0, cursor="hand2")
        self.indicator.pack()
        self.bg_circle = self.indicator.create_oval(18, 18, 58, 58, fill=self.bg,
                                                    outline=PROTON_BORDER, width=2)
        self.fg_rect = self.indicator.create_rectangle(6, 6, 48, 48, fill=self.fg,
                                                       outline=PROTON_PRIMARY, width=2)
        self.indicator.bind("<Button-1>", self.on_indicator_click)
        self.indicator.bind("<Button-3>", lambda e: self.choose_color_secondary())
        self.add_tooltip(self.indicator, "Square: primary color (click to change)\nCircle: secondary color")

        # rainbow + gray gradient
        GW, GH = 300, 44
        grad = Image.new("RGB", (GW, GH))
        gd = ImageDraw.Draw(grad)
        for x in range(GW):
            r, g, b = colorsys.hsv_to_rgb(x / GW, 1.0, 1.0)
            gd.line([(x, 0), (x, 27)], fill=(int(r * 255), int(g * 255), int(b * 255)))
            v = int(255 * x / (GW - 1))
            gd.line([(x, 28), (x, GH - 1)], fill=(v, v, v))
        self.gradient_img = grad
        self.gradient_photo = ImageTk.PhotoImage(grad)
        mid = tk.Frame(bottom, bg=PROTON_DARK_PANEL, pady=10)
        mid.pack(side=tk.LEFT, padx=8)
        self.gradient_canvas = tk.Canvas(mid, width=GW, height=GH, bg=PROTON_DARK_PANEL,
                                         highlightthickness=0, cursor="hand2")
        self.gradient_canvas.pack()
        self.gradient_canvas.create_image(0, 0, image=self.gradient_photo, anchor="nw")
        self.gradient_canvas.bind("<Button-1>", lambda e: self.color_from_gradient(e, True))
        self.gradient_canvas.bind("<B1-Motion>", lambda e: self.color_from_gradient(e, True))
        self.gradient_canvas.bind("<Button-3>", lambda e: self.color_from_gradient(e, False))
        self.gradient_canvas.bind("<B3-Motion>", lambda e: self.color_from_gradient(e, False))
        self.add_tooltip(self.gradient_canvas, "Left click: primary\nRight click: secondary")

        # palette 10 x 2
        pal = tk.Frame(bottom, bg=PROTON_DARK_PANEL, pady=10)
        pal.pack(side=tk.LEFT, padx=8)
        for i, col in enumerate(PALETTE):
            lbl = tk.Label(pal, bg=col, width=3, height=1, cursor="hand2",
                           highlightthickness=1, highlightbackground=PROTON_BORDER)
            lbl.grid(row=i // 10, column=i % 10, padx=2, pady=2)
            lbl.bind("<Button-1>", lambda e, c=col: self.set_fg(c))
            lbl.bind("<Button-3>", lambda e, c=col: self.set_bg(c))

        # more + recent
        right = tk.Frame(bottom, bg=PROTON_DARK_PANEL, pady=10)
        right.pack(side=tk.LEFT, padx=8)
        tk.Button(right, text="More colors...", command=self.choose_color_primary,
                  bg=PROTON_PRIMARY, fg="white", relief=tk.FLAT, bd=0, padx=10, pady=4,
                  font=("Helvetica", 9), cursor="hand2",
                  activebackground=PROTON_PRIMARY_DARK, activeforeground="white").pack(anchor="w")
        tk.Label(right, text="RECENT", bg=PROTON_DARK_PANEL, fg=PROTON_TEXT_MUTED,
                 font=("Helvetica", 8)).pack(anchor="w", pady=(6, 0))
        self.history_frame = tk.Frame(right, bg=PROTON_DARK_PANEL)
        self.history_frame.pack(anchor="w", pady=2)
        self.update_recent_colors()

        # ===== CENTER CANVAS =====
        center = tk.Frame(self.root, bg=PROTON_DARK_BG)
        center.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(center, bg="#0c0d10", highlightthickness=0,
                                cursor="crosshair", relief=tk.FLAT)
        vs = ttk.Scrollbar(center, orient=tk.VERTICAL, command=self.canvas.yview)
        hs = ttk.Scrollbar(center, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        vs.pack(side=tk.RIGHT, fill=tk.Y)
        hs.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.photo = ImageTk.PhotoImage(self.img)
        self.img_id = self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        for b in (1, 3):
            self.canvas.bind(f"<ButtonPress-{b}>", self.on_press)
            self.canvas.bind(f"<B{b}-Motion>", self.on_drag)
            self.canvas.bind(f"<ButtonRelease-{b}>", self.on_release)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.zoom_in)
        self.canvas.bind("<Button-5>", self.zoom_out)

    def key_zoom(self, fn):
        def handler(e):
            if isinstance(e.widget, (tk.Entry, tk.Text, ttk.Entry)):
                return
            fn()
        return handler

    def bind_keys(self):
        r = self.root
        r.bind_all("<Control-n>", lambda e: self.new_image())
        r.bind_all("<Control-o>", lambda e: self.open_image())
        r.bind_all("<Control-s>", lambda e: self.save())
        r.bind_all("<Control-S>", lambda e: self.save_as())
        r.bind_all("<Control-z>", lambda e: self.undo())
        r.bind_all("<Control-y>", lambda e: self.redo())
        r.bind_all("<Control-c>", lambda e: self.copy_to_clipboard())
        r.bind_all("<Control-v>", lambda e: self.paste_from_clipboard())
        r.bind_all("<Control-q>", lambda e: self.quit())
        r.bind_all("<Control-F>", lambda e: self.take_screenshot(area=False))
        r.bind_all("<Control-A>", lambda e: self.take_screenshot(area=True))
        r.bind_all("<plus>", self.key_zoom(self.zoom_in))
        r.bind_all("<minus>", self.key_zoom(self.zoom_out))
        r.bind_all("<Key-0>", self.key_zoom(self.zoom_reset))
        r.bind_all("<Escape>", lambda e: self.cancel_operation())

    # ============================================================ TOOLTIPS
    def show_tooltip(self, widget, text):
        self.hide_tooltip()
        x = widget.winfo_rootx() + 10
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        self.tooltip_window = tk.Toplevel(widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tooltip_window, text=text, bg=PROTON_DARK_BG, fg=PROTON_TEXT_MAIN,
                 font=("Helvetica", 9), relief=tk.SOLID, padx=8, pady=4, borderwidth=1,
                 justify=tk.LEFT, wraplength=260).pack()

    def hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def add_tooltip(self, widget, text):
        widget.bind("<Enter>", lambda e: self.show_tooltip(widget, text), add="+")
        widget.bind("<Leave>", lambda e: self.hide_tooltip(), add="+")
        widget.bind("<ButtonPress>", lambda e: self.hide_tooltip(), add="+")

    # ============================================================== COLORS
    def _remember(self, color):
        if color not in self.recent_colors[:1]:
            if color in self.recent_colors:
                self.recent_colors.remove(color)
            self.recent_colors.insert(0, color)
            self.recent_colors = self.recent_colors[:6]
            self.update_recent_colors()

    def set_fg(self, color):
        self.fg = color
        self.indicator.itemconfig(self.fg_rect, fill=color)
        self._remember(color)
        self.save_settings()

    def set_bg(self, color):
        self.bg = color
        self.indicator.itemconfig(self.bg_circle, fill=color)
        self._remember(color)
        self.save_settings()

    def on_indicator_click(self, event):
        if 6 <= event.x <= 48 and 6 <= event.y <= 48:
            self.choose_color_primary()
        else:
            self.choose_color_secondary()

    def choose_color_primary(self):
        c = colorchooser.askcolor(color=self.fg, title="Primary color")
        if c and c[1]:
            self.set_fg(c[1])

    def choose_color_secondary(self):
        c = colorchooser.askcolor(color=self.bg, title="Secondary color")
        if c and c[1]:
            self.set_bg(c[1])

    def color_from_gradient(self, event, primary=True):
        x = max(0, min(event.x, self.gradient_img.width - 1))
        y = max(0, min(event.y, self.gradient_img.height - 1))
        r, g, b = self.gradient_img.getpixel((x, y))
        color = "#{:02x}{:02x}{:02x}".format(r, g, b)
        (self.set_fg if primary else self.set_bg)(color)

    def update_recent_colors(self):
        for widget in self.history_frame.winfo_children():
            widget.destroy()
        for i, col in enumerate(self.recent_colors[:6]):
            lbl = tk.Label(self.history_frame, bg=col, width=2, height=1, cursor="hand2",
                           highlightthickness=1, highlightbackground=PROTON_BORDER)
            lbl.grid(row=0, column=i, padx=2)
            lbl.bind("<Button-1>", lambda e, c=col: self.set_fg(c))
            lbl.bind("<Button-3>", lambda e, c=col: self.set_bg(c))

    # ============================================================= DISPLAY
    def refresh(self):
        if self.zoom_level == 1.0:
            view = self.img
        else:
            w = max(1, int(self.img.width * self.zoom_level))
            h = max(1, int(self.img.height * self.zoom_level))
            resample = Image.Resampling.NEAREST if self.zoom_level > 1 else Image.Resampling.LANCZOS
            view = self.img.resize((w, h), resample)
        self.photo = ImageTk.PhotoImage(view)
        self.canvas.itemconfig(self.img_id, image=self.photo)
        self.canvas.config(scrollregion=(0, 0, view.width, view.height))

    def update_title(self):
        name = os.path.basename(self.filename) if self.filename else "Untitled"
        mark = "● " if self.modified else ""
        zoom_str = f" [{int(self.zoom_level * 100)}%]" if self.zoom_level != 1.0 else ""
        self.root.title(f"{mark}{name}{zoom_str} - {APP_NAME}")

    def pos(self, event):
        x = int(self.canvas.canvasx(event.x) / self.zoom_level)
        y = int(self.canvas.canvasy(event.y) / self.zoom_level)
        return max(0, min(x, self.img.width - 1)), max(0, min(y, self.img.height - 1))

    def on_motion(self, event):
        x, y = self.pos(event)
        col = self.img.getpixel((x, y))
        col_hex = "#{:02x}{:02x}{:02x}".format(col[0], col[1], col[2])
        self.status.config(
            text=f" X: {x:6d}  Y: {y:6d}  │  RGB({col[0]:3d},{col[1]:3d},{col[2]:3d})  │  {col_hex}  │  {self.img.width}×{self.img.height}"
        )

    # ========================================================== UNDO/REDO
    def push_undo(self):
        self.undo_stack.append(self.img.copy())
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.modified = True
        self.update_title()

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self.img.copy())
        self.img = self.undo_stack.pop()
        self.refresh()

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self.img.copy())
        self.img = self.redo_stack.pop()
        self.refresh()

    # ============================================================= DRAWING
    def on_press(self, event):
        if self.active_text_widget:
            self.finalize_text()

        x, y = self.pos(event)
        if event.num == 1:
            self.cur_color, self.other_color = self.fg, self.bg
        else:
            self.cur_color, self.other_color = self.bg, self.fg
        tool = self.tool.get()

        if tool == "picker":
            col = self.img.getpixel((x, y))
            hex_col = "#{:02x}{:02x}{:02x}".format(col[0], col[1], col[2])
            (self.set_fg if event.num == 1 else self.set_bg)(hex_col)
            return

        if tool == "fill":
            self.push_undo()
            ImageDraw.floodfill(self.img, (x, y), ImageColor.getrgb(self.cur_color), thresh=8)
            self.refresh()
            return

        if tool == "text":
            self.text_start_pos = (event.x, event.y)
            self.text_pil_pos = (x, y)
            self.text_rect_id = self.canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                dash=(4, 4), outline=self.cur_color, width=2)
            return

        self.push_undo()
        self.start = self.last = (x, y)
        if tool in FREEHAND:
            self.stroke(self.last, self.last, tool)
            self.refresh()
        else:
            self.base = self.img.copy()

    def on_drag(self, event):
        tool = self.tool.get()
        if tool == "text":
            if self.text_rect_id:
                self.canvas.coords(self.text_rect_id, self.text_start_pos[0],
                                   self.text_start_pos[1], event.x, event.y)
            return

        if self.start is None:
            return
        self.on_motion(event)
        p = self.pos(event)

        if tool in FREEHAND:
            self.stroke(self.last, p, tool)
            self.last = p
            self.refresh()
        elif tool in SHAPES:
            preview_img = self.base.copy()
            d = ImageDraw.Draw(preview_img)
            test_p = self.constrain(self.start, p, tool) if event.state & 0x0001 else p
            self.draw_shape(d, tool, self.start, test_p)
            self.img = preview_img
            self.refresh()

    def on_release(self, event):
        tool = self.tool.get()
        if tool == "text":
            if self.text_rect_id:
                x0, y0 = self.text_start_pos
                x1, y1 = event.x, event.y
                self.canvas.delete(self.text_rect_id)
                self.text_rect_id = None

                x0, x1 = min(x0, x1), max(x0, x1)
                y0, y1 = min(y0, y1), max(y0, y1)
                w, h = x1 - x0, y1 - y0
                if w < 20 or h < 20:
                    w, h = 200, max(50, self.size.get() * 6)

                pil_font_size = max(12, self.size.get() * 4)
                self.active_text_widget = tk.Text(
                    self.canvas, font=("Helvetica", pil_font_size),
                    fg=self.cur_color, bg="#ffffff", insertbackground=self.cur_color,
                    relief=tk.FLAT, highlightbackground=PROTON_PRIMARY,
                    highlightcolor=PROTON_PRIMARY, highlightthickness=2, wrap=tk.WORD)
                self.active_text_widget.place(x=x0, y=y0, width=w, height=h)
                self.active_text_widget.focus_set()

                self.text_pil_pos = (int(self.canvas.canvasx(x0) / self.zoom_level),
                                     int(self.canvas.canvasy(y0) / self.zoom_level))

                self.active_text_widget.bind("<Shift-Return>", self.finalize_text)
                self.active_text_widget.bind("<Escape>", self.cancel_text)
                self.status.config(text="Text: Shift+Enter to confirm, Esc to cancel")
            return

        self.start = self.last = self.base = None

    def finalize_text(self, event=None):
        if not self.active_text_widget:
            return "break"

        text = self.active_text_widget.get("1.0", tk.END).strip()
        self.active_text_widget.destroy()
        self.active_text_widget = None

        if text:
            self.push_undo()
            d = ImageDraw.Draw(self.img)
            font = load_font(max(12, self.size.get() * 4))
            d.multiline_text(self.text_pil_pos, text, fill=self.cur_color, font=font)
            self.refresh()

        self.status.config(text="Ready")
        return "break"

    def cancel_text(self, event=None):
        if self.active_text_widget:
            self.active_text_widget.destroy()
            self.active_text_widget = None
            self.status.config(text="Ready")
        return "break"

    def stroke(self, p0, p1, tool):
        d = ImageDraw.Draw(self.img)
        size = self.size.get()
        if tool == "spray":
            radius = size * 3
            for _ in range(size * 5):
                ang = random.uniform(0, 2 * math.pi)
                r = radius * math.sqrt(random.random())
                x = p1[0] + r * math.cos(ang)
                y = p1[1] + r * math.sin(ang)
                d.point((x, y), fill=self.cur_color)
            return
        if tool == "pencil":
            w, color = 1, self.cur_color
        elif tool == "eraser":
            w, color = size * 2, self.bg
        else:
            w, color = max(1, size), self.cur_color
        d.line([p0, p1], fill=color, width=w, joint="round")
        if w > 1:
            r = w / 2
            d.ellipse([p1[0] - r, p1[1] - r, p1[0] + r, p1[1] + r], fill=color)

    def draw_shape(self, d, tool, p0, p1):
        size = self.size.get()
        if tool == "line":
            d.line([p0, p1], fill=self.cur_color, width=max(1, size), joint="round")
            return
        box = [min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])]
        mode = self.fill_mode.get()
        if mode == "outline":
            fill, outline = None, self.cur_color
        elif mode == "filled":
            fill, outline = self.cur_color, self.cur_color
        else:
            fill, outline = self.other_color, self.cur_color
        if tool == "rect":
            d.rounded_rectangle(box, radius=min(10, size), fill=fill, outline=outline, width=max(1, size))
        else:
            d.ellipse(box, fill=fill, outline=outline, width=max(1, size))

    @staticmethod
    def constrain(p0, p1, tool):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        if tool == "line":
            step = math.pi / 4
            ang = round(math.atan2(dy, dx) / step) * step
            dist = math.hypot(dx, dy)
            return (p0[0] + round(dist * math.cos(ang)),
                    p0[1] + round(dist * math.sin(ang)))
        m = max(abs(dx), abs(dy))
        return (p0[0] + (m if dx >= 0 else -m),
                p0[1] + (m if dy >= 0 else -m))

    # ======================================================== OPERATIONS
    def clear_all(self):
        if messagebox.askyesno("Confirm", "Clear all content?"):
            self.push_undo()
            self.img = Image.new("RGB", self.img.size, self.bg)
            self.refresh()

    def transform(self, kind):
        self.finalize_text()
        self.push_undo()
        if kind == "rot_l":
            self.img = self.img.rotate(90, expand=True, fillcolor=self.bg)
        elif kind == "rot_r":
            self.img = self.img.rotate(-90, expand=True, fillcolor=self.bg)
        elif kind == "mirror":
            self.img = ImageOps.mirror(self.img)
        elif kind == "flip":
            self.img = ImageOps.flip(self.img)
        elif kind == "invert":
            self.img = ImageOps.invert(self.img)
        elif kind == "grayscale":
            self.img = ImageOps.grayscale(self.img).convert("RGB")
        elif kind == "contrast_up":
            self.img = ImageEnhance.Contrast(self.img).enhance(1.3)
        self.refresh()

    def resize_canvas(self):
        self.finalize_text()
        w = simpledialog.askinteger("Resize", "Width (px):",
                                    initialvalue=self.img.width, minvalue=100, maxvalue=8000,
                                    parent=self.root)
        if not w:
            return
        h = simpledialog.askinteger("Resize", "Height (px):",
                                    initialvalue=self.img.height, minvalue=100, maxvalue=8000,
                                    parent=self.root)
        if not h:
            return
        self.push_undo()
        new = Image.new("RGB", (w, h), "white")
        new.paste(self.img, (0, 0))
        self.img = new
        self.refresh()

    def zoom_in(self, event=None):
        self.finalize_text()
        self.zoom_level = min(self.zoom_level * 1.25, 8.0)
        self.refresh()
        self.update_title()

    def zoom_out(self, event=None):
        self.finalize_text()
        self.zoom_level = max(self.zoom_level / 1.25, 0.125)
        self.refresh()
        self.update_title()

    def zoom_reset(self, event=None):
        self.finalize_text()
        self.zoom_level = 1.0
        self.refresh()
        self.update_title()

    def copy_to_clipboard(self):
        try:
            from PIL import ImageGrab  # noqa: F401
            self.img.show()
            messagebox.showinfo("Copy", "Image copied")
        except ImportError:
            messagebox.showwarning("Notice", "Install full Pillow for clipboard")

    def paste_from_clipboard(self):
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img:
                self.push_undo()
                self.img = img.convert("RGB")
                self.refresh()
        except ImportError:
            messagebox.showwarning("Notice", "Install full Pillow for clipboard")

    def cancel_operation(self):
        self.cancel_text()
        self.start = self.last = self.base = None
        self.hide_tooltip()

    # ============================================================ SCREENSHOT
    def set_window_icon(self):
        path = find_icon()
        if path:
            try:
                self._icon = tk.PhotoImage(file=path)
                self.root.iconphoto(True, self._icon)
            except tk.TclError:
                pass

    def take_screenshot(self, area=False, delay=None, from_cli=False):
        if delay is None:
            delay = self.delay.get()
        self.root.withdraw()
        self.root.after(1000 + int(delay) * 1000, lambda: self._capture(area, from_cli))

    def _capture(self, area, from_cli):
        shot, error = None, None
        try:
            shot = grab_screen()
            if area:
                shot = self.select_area(shot)
        except Exception as e:
            error = str(e)

        if shot is None and not error:
            if from_cli:
                self.root.destroy()
            else:
                self.root.deiconify()
            return

        self.root.deiconify()
        self.root.lift()
        if error:
            messagebox.showerror(APP_NAME, f"Screenshot error:\n{error}")
            if from_cli:
                self.root.destroy()
            return

        self.push_undo()
        self.img = shot
        self.refresh()

        save_dir = os.path.expanduser("~/Pictures/Screenshots")
        os.makedirs(save_dir, exist_ok=True)
        filename = time.strftime("Screenshot_%Y-%m-%d_%H-%M-%S.png")
        filepath = os.path.join(save_dir, filename)

        try:
            self.img.save(filepath)
            self.filename = filepath
            self.modified = False
            self.status.config(text=f"✓ Saved: {os.path.basename(filepath)}")
            if from_cli:
                self.root.after(1500, self.quit)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Save failed:\n{e}")
            self.filename = None
            self.modified = True
            self.status.config(text="✓ Screenshot captured")

        self.update_title()

    def select_area(self, shot):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        sx, sy = shot.width / sw, shot.height / sh

        top = tk.Toplevel(self.root)
        top.attributes("-fullscreen", True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", 1.0)
        top.lift()
        top.focus_force()

        cv = tk.Canvas(top, width=sw, height=sh, highlightthickness=0,
                       cursor="crosshair", bg="#08090b")
        cv.pack(fill=tk.BOTH, expand=True)

        dim = ImageEnhance.Brightness(shot.resize((sw, sh))).enhance(0.35)
        top._dim = ImageTk.PhotoImage(dim)
        cv.create_image(0, 0, image=top._dim, anchor="nw")

        # Hint bar: slim, glued to the bottom edge (away from the GNOME "screenshot taken" popup),
        # and removed as soon as the drag starts.
        bw, bh = 520, 58
        by = sh - 24 - bh // 2
        cv.create_rectangle(sw // 2 - bw // 2, by - bh // 2, sw // 2 + bw // 2, by + bh // 2,
                            fill=PROTON_DARK_BG, outline=PROTON_PRIMARY, width=2, tags="banner")
        cv.create_text(sw // 2, by - 9, text="DRAG TO SELECT AREA  •  ESC to cancel",
                       fill="white", font=("Helvetica", 14, "bold"), tags="banner")
        cv.create_text(sw // 2, by + 14, text="Selection will be loaded into the editor",
                       fill=PROTON_TEXT_MUTED, font=("Helvetica", 10), tags="banner")

        st = {"p0": None, "img": None, "rect": None, "dims": None}
        result = {"box": None}

        def clamp(e):
            return max(0, min(sw, e.x)), max(0, min(sh, e.y))

        def make_box(e):
            x0, y0 = st["p0"]
            x1, y1 = clamp(e)
            return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

        def press(e):
            cv.delete("banner")
            st["p0"] = clamp(e)

        def release(e):
            if st["p0"]:
                box = make_box(e)
                if box[2] - box[0] >= 4 and box[3] - box[1] >= 4:
                    result["box"] = box
            top.destroy()

        def motion(e):
            if st["p0"]:
                box = make_box(e)
                if box[2] - box[0] < 1 or box[3] - box[1] < 1:
                    return
                crop = shot.crop((round(box[0] * sx), round(box[1] * sy),
                                  round(box[2] * sx), round(box[3] * sy)))
                top._bright = ImageTk.PhotoImage(crop)
                dims = f"{round((box[2] - box[0]) * sx)} × {round((box[3] - box[1]) * sy)}"
                if st["img"] is None:
                    st["img"] = cv.create_image(round(box[0]), round(box[1]),
                                                image=top._bright, anchor="nw")
                    st["rect"] = cv.create_rectangle(*box, outline=PROTON_PRIMARY, width=3)
                    st["dims"] = cv.create_text(box[0] + 8, max(20, box[1] - 8), anchor="w",
                                                fill="white", font=("Monospace", 12, "bold"),
                                                text=dims)
                else:
                    cv.itemconfig(st["img"], image=top._bright)
                    cv.coords(st["img"], round(box[0]), round(box[1]))
                    cv.coords(st["rect"], *box)
                    cv.coords(st["dims"], box[0] + 8, max(20, box[1] - 8))
                    cv.itemconfig(st["dims"], text=dims)

        cv.bind("<ButtonPress-1>", press)
        cv.bind("<B1-Motion>", motion)
        cv.bind("<ButtonRelease-1>", release)
        top.bind("<Escape>", lambda e: top.destroy())

        try:
            top.grab_set()
        except tk.TclError:
            pass

        self.root.wait_window(top)

        box = result["box"]
        if not box:
            return None
        return shot.crop((round(box[0] * sx), round(box[1] * sy),
                          round(box[2] * sx), round(box[3] * sy)))

    # ================================================================ FILES
    def confirm_discard(self):
        if not self.modified:
            return True
        ans = messagebox.askyesnocancel(
            APP_NAME,
            f"Save before exiting?\n\n'{os.path.basename(self.filename) if self.filename else 'Untitled'}'")
        if ans is None:
            return False
        if ans:
            return self.save()
        return True

    def new_image(self):
        if not self.confirm_discard():
            return
        w = simpledialog.askinteger("New", "Width (px):", initialvalue=1920,
                                    minvalue=100, maxvalue=8000, parent=self.root)
        if not w:
            return
        h = simpledialog.askinteger("New", "Height (px):", initialvalue=1080,
                                    minvalue=100, maxvalue=8000, parent=self.root)
        if not h:
            return
        self.img = Image.new("RGB", (w, h), "white")
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.filename = None
        self.modified = False
        self.zoom_level = 1.0
        self.refresh()
        self.update_title()

    def load_file(self, path):
        try:
            self.img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Cannot open file:\n{e}")
            return
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.filename = path
        self.modified = False
        self.refresh()
        self.update_title()

    def open_image(self):
        if not self.confirm_discard():
            return
        initial_dir = os.path.expanduser("~/Pictures")
        path = filedialog.askopenfilename(
            title="Open image",
            initialdir=initial_dir if os.path.exists(initial_dir) else os.path.expanduser("~"),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff *.ico"),
                       ("All files", "*.*")])
        if path:
            self.load_file(path)

    def save(self):
        if not self.filename:
            return self.save_as()
        return self.write_file(self.filename)

    def save_as(self):
        initial_dir = os.path.expanduser("~/Pictures")
        path = filedialog.asksaveasfilename(
            title="Save As",
            initialdir=initial_dir if os.path.exists(initial_dir) else os.path.expanduser("~"),
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg"),
                       ("BMP", "*.bmp"), ("WebP", "*.webp"),
                       ("TIFF", "*.tif *.tiff"), ("All", "*.*")])
        if not path:
            return False
        return self.write_file(path)

    def save_format(self, fmt):
        ext_map = {"PNG": ".png", "JPEG": ".jpg", "BMP": ".bmp", "WebP": ".webp"}
        initial_dir = os.path.expanduser("~/Pictures")
        path = filedialog.asksaveasfilename(
            title=f"Export as {fmt}",
            initialdir=initial_dir if os.path.exists(initial_dir) else os.path.expanduser("~"),
            defaultextension=ext_map.get(fmt, ".png"),
            filetypes=[(fmt, "*" + ext_map.get(fmt, ".*")), ("All", "*.*")])
        if path:
            self.write_file(path)

    def write_file(self, path):
        try:
            if path.lower().endswith((".jpg", ".jpeg")):
                self.img.save(path, quality=95)
            else:
                self.img.save(path)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Cannot save:\n{e}")
            return False
        self.filename = path
        self.modified = False
        self.update_title()
        self.status.config(text=f"✓ Saved: {os.path.basename(path)}")
        return True

    def quit(self):
        if self.confirm_discard():
            self.save_settings()
            self.root.destroy()

    def about(self):
        messagebox.showinfo(
            f"{APP_NAME} v{APP_VERSION}",
            f"LinPaint+ - Modern drawing app for Linux\n\n"
            f"Version: {APP_VERSION}\n\n"
            f"Tips:\n"
            f"• Right click = secondary color\n"
            f"• Shift = 45° lines / squares / circles\n"
            f"• Scroll wheel = zoom\n\n"
            f"Shortcuts:\n"
            f"• Ctrl+N/O/S/Z/Y - New/Open/Save/Undo/Redo\n"
            f"• Ctrl+Shift+F/A - Full screen/Area\n"
            f"• +/-/0 - Zoom\n\n"
            f"MIT License")

    def on_mousewheel(self, event):
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()


def main():
    parser = argparse.ArgumentParser(
        description="LinPaint+ - Modern drawing editor",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", nargs="?", help="image to open")
    parser.add_argument("--screenshot", action="store_true",
                        help="capture screen and open for editing")
    parser.add_argument("--area", action="store_true",
                        help="with --screenshot: select area only")
    parser.add_argument("--delay", type=int, default=0, metavar="SEC",
                        help="delay seconds before capture")
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    args = parser.parse_args()

    root = tk.Tk(className="LinPaint")
    root.title(APP_NAME)
    root.geometry("1300x880")
    root.minsize(900, 700)

    if args.screenshot:
        root.withdraw()

    app = LinPaint(root, args.file)
    if args.screenshot:
        root.after(50, lambda: app.take_screenshot(area=args.area, delay=args.delay, from_cli=True))

    root.mainloop()


if __name__ == "__main__":
    main()
