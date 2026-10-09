#!/usr/bin/env python3
"""
Aurora - Ultimate Carbon Dark Edition
Privacy: zero network access, 100% offline
"""
import os
import random
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

# Must be set before QApplication is created (setdefault: lets the user override it)
os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QSlider, QFrame,
    QMenu, QFileDialog, QSplitter, QLineEdit, QInputDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QProgressDialog, QStyle, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QSocketNotifier, QUrl, QSettings, QThread, pyqtSignal,
    QRectF, QRect, QPointF,
)
from PyQt6.QtGui import (
    QAction, QIcon, QColor, QKeySequence, QShortcut, QPainter, QBrush,
    QLinearGradient, QPixmap, QPainterPath, QPalette, QPolygonF,
)

try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    USE_QT = True
except ImportError:
    USE_QT = False

import mutagen

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
APP_DIR = Path.home() / ".aurora"
DB_PATH = APP_DIR / "library.db"
ICON_PATH = APP_DIR / "icon.svg"
AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav"}
AUDIO_FILTER = "Audio (*.mp3 *.flac *.ogg *.opus *.m4a *.wav);;All Files (*)"
SOCKET_NAME = f"\0aurora_lock_{os.getuid()}"   # per-user single-instance socket

ACCENT = "#6ee7c8"     # aurora teal
ACCENT2 = "#8b7cff"    # aurora violet
GRAY = "#505055"

STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0b0b0e;
    color: #e2e2e5;
    font-family: system-ui, sans-serif;
}
QToolTip {
    background-color: #15151a; color: #e2e2e5;
    border: 1px solid #2a2a32; padding: 4px;
}
QMenuBar { background-color: #0b0b0e; color: #a0a0a5; }
QMenuBar::item { padding: 6px 10px; background: transparent; border-radius: 6px; }
QMenuBar::item:selected { background-color: #1c1c22; color: #ffffff; }
QMenu {
    background-color: #15151a; color: #e2e2e5;
    border: 1px solid #222228; padding: 4px;
}
QMenu::item { padding: 6px 24px; border-radius: 4px; }
QMenu::item:selected { background-color: #2a2a32; }
QMenu::item:disabled { color: #505055; }
QMenu::separator { height: 1px; background: #222228; margin: 4px 8px; }
QStatusBar { background-color: #0b0b0e; color: #707075; font-size: 12px; }
QStatusBar::item { border: none; }
QSplitter::handle { background-color: #0b0b0e; }
QListWidget, QTableWidget {
    background-color: #0b0b0e;
    border: none;
    outline: none;
    font-size: 14px;
}
QListWidget::item {
    padding: 10px;
    border-radius: 6px;
    margin: 2px 8px;
    color: #a0a0a5;
}
QListWidget::item:selected {
    background-color: #1c1c22;
    color: #ffffff;
    font-weight: 600;
    border-left: 3px solid %ACCENT%;
}
QListWidget::item:hover:!selected { background-color: #15151a; }
QTableWidget::item { padding: 8px 5px; border-bottom: 1px solid #15151a; }
QTableWidget::item:selected { background-color: #1c1c22; color: #ffffff; }
QHeaderView::section {
    background-color: #0b0b0e;
    color: #707075;
    border: none;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 5px;
}
QPushButton {
    background-color: transparent;
    color: #a0a0a5;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover { color: #ffffff; background-color: #1c1c22; }
QPushButton:checked { color: %ACCENT%; background-color: #1c1c22; }
QLineEdit {
    background-color: #15151a;
    border: 1px solid #222228;
    border-radius: 18px;
    padding: 8px 15px;
    color: #ffffff;
    font-size: 14px;
}
QLineEdit:focus { border: 1px solid %ACCENT2%; }
QSlider::groove:horizontal { border-radius: 2px; height: 4px; background: #222228; }
QSlider::sub-page:horizontal {
    border-radius: 2px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 %ACCENT%, stop:1 %ACCENT2%);
}
QSlider::handle:horizontal {
    background: #ffffff; width: 12px; margin: -4px 0; border-radius: 6px;
}
QSlider::handle:horizontal:hover { background: %ACCENT%; }
QScrollBar:vertical { background: #0b0b0e; width: 12px; margin: 0; }
QScrollBar::handle:vertical {
    background: #2a2a32; border-radius: 6px; min-height: 30px; margin: 2px;
}
QScrollBar::handle:vertical:hover { background: #3a3a42; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QProgressBar {
    background: #15151a; border: none; border-radius: 4px; text-align: center; height: 8px;
}
QProgressBar::chunk { background: %ACCENT%; border-radius: 4px; }
QFrame#playerBar { background-color: #111115; border-radius: 12px; }
QFrame#playerBar QLabel, QFrame#playerBar QSlider { background: transparent; }
QPushButton#playBtn {
    min-width: 46px; max-width: 46px; min-height: 46px; max-height: 46px;
    border-radius: 23px; padding: 0;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 %ACCENT%, stop:1 %ACCENT2%);
}
QPushButton#playBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9af5de, stop:1 #a99dff);
}
QPushButton#transportBtn { padding: 8px; border-radius: 18px; }
QLabel#section {
    color: #707075; font-size: 12px; font-weight: 600; letter-spacing: 1px;
}
""".replace("%ACCENT%", ACCENT).replace("%ACCENT2%", ACCENT2)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def fmt_time(s):
    """m:ss, or h:mm:ss for tracks of an hour or more."""
    if not s or s <= 0:
        return "0:00"
    s = int(s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fmt_long(s):
    s = int(s or 0)
    h, rem = divmod(s, 3600)
    m = rem // 60
    return f"{h}h {m:02d}m" if h else f"{m}m"


def escape_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def expand_paths(paths, strict=True):
    """Absolute, de-duplicated list of audio files; folders are walked recursively."""
    out, seen = [], set()

    def add(fp):
        if fp not in seen:
            seen.add(fp)
            out.append(fp)

    for p in paths:
        p = os.path.abspath(p)
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    if os.path.splitext(f)[1].lower() in AUDIO_EXTS:
                        add(os.path.join(root, f))
        elif os.path.isfile(p):
            if not strict or os.path.splitext(p)[1].lower() in AUDIO_EXTS:
                add(p)
    return out


def read_meta(path):
    """Read tags + duration. Safe to call from a worker thread (no Qt objects)."""
    title, artist, album, duration = Path(path).stem, "Unknown", "", 0.0
    try:
        audio = mutagen.File(path, easy=True)
        if audio is not None:
            title = (audio.get("title") or [title])[0]
            artist = (audio.get("artist") or [artist])[0]
            album = (audio.get("album") or [""])[0]
            info = getattr(audio, "info", None)
            duration = float(getattr(info, "length", 0) or 0)
    except Exception:
        pass

    if duration <= 0 and shutil.which("ffprobe"):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=5)
            if r.stdout.strip():
                duration = float(r.stdout.strip())
        except Exception:
            duration = 0.0
    return {"path": str(path), "title": str(title), "artist": str(artist),
            "album": str(album), "duration": duration}


def read_cover(path):
    """Embedded cover art (ID3 APIC / FLAC picture) or cover.jpg/folder.jpg next to the file."""
    data = None
    try:
        f = mutagen.File(path)
        if f is not None:
            if getattr(f, "pictures", None):
                data = f.pictures[0].data
            elif f.tags:
                for k in f.tags.keys():
                    if str(k).startswith("APIC"):
                        data = f.tags[k].data
                        break
    except Exception:
        data = None

    pm = QPixmap()
    if data and pm.loadFromData(data):
        return pm
    folder = Path(path).parent
    for name in ("cover", "folder", "front", "album"):
        for ext in (".jpg", ".jpeg", ".png"):
            cand = folder / f"{name}{ext}"
            if cand.exists() and pm.load(str(cand)):
                return pm
    return None


def transport_icon(kind, color="#e2e2e5"):
    """Hand-drawn transport icons: no dependency on font glyphs or icon themes."""
    size = 48
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    if kind == "play":
        p.drawPolygon(QPolygonF([QPointF(15, 8), QPointF(40, 24), QPointF(15, 40)]))
    elif kind == "pause":
        p.drawRoundedRect(QRectF(11, 9, 10, 30), 2, 2)
        p.drawRoundedRect(QRectF(27, 9, 10, 30), 2, 2)
    elif kind == "prev":
        p.drawRoundedRect(QRectF(8, 10, 5, 28), 2, 2)
        p.drawPolygon(QPolygonF([QPointF(40, 10), QPointF(17, 24), QPointF(40, 38)]))
    elif kind == "next":
        p.drawPolygon(QPolygonF([QPointF(8, 10), QPointF(31, 24), QPointF(8, 38)]))
        p.drawRoundedRect(QRectF(35, 10, 5, 28), 2, 2)
    p.end()
    return QIcon(pm)


# --------------------------------------------------------------------------
# Widgets
# --------------------------------------------------------------------------
class SortItem(QTableWidgetItem):
    """Table item with an explicit sort key (numeric durations, case-insensitive text)."""
    def __init__(self, text, key=None):
        super().__init__(text)
        self._key = text.lower() if key is None else key

    def __lt__(self, other):
        if isinstance(other, SortItem):
            return self._key < other._key
        return super().__lt__(other)


class SeekSlider(QSlider):
    """Horizontal slider that jumps to the clicked position."""
    seekRequested = pyqtSignal(int)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.maximum() > 0:
            val = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(), int(e.position().x()), self.width())
            self.setValue(val)
            self.seekRequested.emit(val)
        super().mousePressEvent(e)


class SpectrumAnalyzer(QWidget):
    """Decorative spectrum (simulated: Qt Multimedia does not expose raw samples)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.n = 36
        self.values = [0.0] * self.n
        self.targets = [0.0] * self.n
        self.peaks = [0.0] * self.n
        self.is_playing = False
        self.frame = 0
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._animate)

    def set_playing(self, state):
        self.is_playing = state
        if state and not self.timer.isActive():
            self.timer.start()

    def _animate(self):
        self.frame += 1
        n = self.n
        if self.is_playing:
            beat = self.frame % 14 == 0
            for i in range(n):
                env = 1.0 - 0.65 * abs((i - n / 2) / (n / 2))
                if beat and i < n * 0.4:
                    self.targets[i] = random.uniform(0.6, 1.0) * env
                elif random.random() < 0.3:
                    self.targets[i] = random.uniform(0.1, 0.9) * env

        busy = False
        for i in range(n):
            t, v = self.targets[i], self.values[i]
            v += (t - v) * (0.55 if t > v else 0.14)      # fast attack, slow release
            self.values[i] = v
            self.targets[i] = t * 0.88
            self.peaks[i] = max(self.peaks[i] - 0.012, v)
            if v > 0.005 or self.peaks[i] > 0.005:
                busy = True
        self.update()
        if not busy and not self.is_playing:
            self.timer.stop()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        slot = w / self.n
        gap = max(1.5, slot * 0.25)
        bw = slot - gap
        grad = QLinearGradient(0, h, 0, 0)
        grad.setColorAt(0.0, QColor(ACCENT2))
        grad.setColorAt(1.0, QColor(ACCENT))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        for i in range(self.n):
            x = i * slot + gap / 2
            bh = max(2.0, self.values[i] * h * 0.92)
            p.drawRoundedRect(QRectF(x, h - bh, bw, bh), 2, 2)
        p.setBrush(QColor(255, 255, 255, 170))
        for i in range(self.n):
            if self.peaks[i] > 0.03:
                x = i * slot + gap / 2
                y = h - self.peaks[i] * h * 0.92 - 4
                p.drawRoundedRect(QRectF(x, y, bw, 2), 1, 1)


class CoverArt(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.setMinimumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_pixmap(self, pm):
        self.pixmap = pm
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        side = min(self.width(), self.height())
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        p.setClipPath(path)
        if self.pixmap:
            s = int(side)
            scaled = self.pixmap.scaled(
                s, s, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            sx, sy = (scaled.width() - s) // 2, (scaled.height() - s) // 2
            p.drawPixmap(rect.toRect(), scaled, QRect(sx, sy, s, s))
        else:
            g = QLinearGradient(rect.topLeft(), rect.bottomRight())
            g.setColorAt(0.0, QColor("#1c1c22"))
            g.setColorAt(1.0, QColor("#111115"))
            p.fillRect(rect, QBrush(g))
            f = p.font()
            f.setPixelSize(int(side * 0.45))
            p.setFont(f)
            p.setPen(QColor("#2f2f38"))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "\u266a")


class ScanWorker(QThread):
    """Reads tags off the GUI thread so big folders don't freeze the window."""
    progress = pyqtSignal(int)
    scanned = pyqtSignal(dict)

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = paths

    def run(self):
        for i, p in enumerate(self.paths, 1):
            if self.isInterruptionRequested():
                break
            self.scanned.emit(read_meta(p))
            self.progress.emit(i)


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------
class Aurora(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aurora Music Player")
        self.setMinimumSize(1100, 720)
        self.setAcceptDrops(True)

        self.settings = QSettings("Aurora", "Aurora")
        self.last_dir = str(self.settings.value("last_dir", str(Path.home())))
        self.is_seeking = False
        self.lock_socket = None
        self.notifier = None
        self.current_path = None
        self.history = []
        self.scan_worker = None
        self.scan_dialog = None
        self._import_target = 0
        self._import_count = 0

        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self._init_db()

        if USE_QT:
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.player.setAudioOutput(self.audio)
            self.player.positionChanged.connect(self._on_position_changed)
            self.player.durationChanged.connect(self._on_duration_changed)
            self.player.mediaStatusChanged.connect(self._on_media_status_changed)
            self.player.playbackStateChanged.connect(self._on_state_changed)
            self.player.errorOccurred.connect(self._on_player_error)
        else:
            self.player = None
            self.audio = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(self._refresh_table)

        self._setup_ui()
        self._setup_menu()
        self._load_sidebar()
        self._restore_settings()

        if not USE_QT:
            self.statusBar().showMessage("Qt Multimedia not available: playback disabled")

    # ---- database -------------------------------------------------------
    def _init_db(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute('''CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY, path TEXT UNIQUE, title TEXT, artist TEXT, duration REAL)''')
        self.conn.execute('''CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
        self.conn.execute('''CREATE TABLE IF NOT EXISTS playlist_tracks (
            playlist_id INTEGER, track_id INTEGER,
            FOREIGN KEY(playlist_id) REFERENCES playlists(id),
            FOREIGN KEY(track_id) REFERENCES tracks(id),
            UNIQUE(playlist_id, track_id))''')
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(tracks)")}
        if "album" not in cols:                       # migrate older libraries
            self.conn.execute("ALTER TABLE tracks ADD COLUMN album TEXT DEFAULT ''")
        self.conn.commit()

    def _upsert_track(self, meta):
        """Insert or refresh a track; returns its id."""
        self.conn.execute(
            '''INSERT INTO tracks (path, title, artist, album, duration) VALUES (?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET title=excluded.title, artist=excluded.artist,
               album=excluded.album, duration=excluded.duration''',
            (meta["path"], meta["title"], meta["artist"], meta["album"], meta["duration"]))
        row = self.conn.execute("SELECT id FROM tracks WHERE path=?", (meta["path"],)).fetchone()
        return row[0] if row else None

    # ---- settings -------------------------------------------------------
    def _restore_settings(self):
        vol = int(self.settings.value("volume", 70))
        self.vol_slider.setValue(vol)
        self.set_vol(vol)                    # explicit: setValue emits nothing if unchanged
        self.btn_shuffle.setChecked(self.settings.value("shuffle", False, type=bool))
        self.btn_repeat.setChecked(self.settings.value("repeat", False, type=bool))
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        st = self.settings.value("splitter")
        if st is not None:
            self.splitter.restoreState(st)

    def closeEvent(self, event):
        self.settings.setValue("volume", self.vol_slider.value())
        self.settings.setValue("shuffle", self.btn_shuffle.isChecked())
        self.settings.setValue("repeat", self.btn_repeat.isChecked())
        self.settings.setValue("last_dir", self.last_dir)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
        if self.scan_worker is not None:
            self.scan_worker.requestInterruption()
            self.scan_worker.wait(3000)
        if self.player:
            self.player.stop()
        self.conn.commit()
        self.conn.close()
        super().closeEvent(event)

    # ---- single instance IPC ---------------------------------------------
    def setup_ipc(self, lock_socket):
        self.lock_socket = lock_socket
        self.lock_socket.setblocking(False)
        self.notifier = QSocketNotifier(self.lock_socket.fileno(), QSocketNotifier.Type.Read, self)
        self.notifier.activated.connect(self._handle_ipc)

    def _handle_ipc(self):
        try:
            data, _ = self.lock_socket.recvfrom(65536)
        except OSError:
            return
        paths = [p for p in data.decode("utf-8", "replace").split("\n") if p and os.path.exists(p)]
        if paths:
            self.open_external_files(paths)
        self.show()
        self.raise_()
        self.activateWindow()

    def open_external_files(self, paths):
        files = expand_paths(paths, strict=False)
        if not files:
            return
        for f in files:
            self._upsert_track(read_meta(f))
        self.conn.commit()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.sidebar.setCurrentRow(0)
        self._refresh_table()
        self.play(files[0])

    # ---- UI --------------------------------------------------------------
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 10)

        # header
        top = QHBoxLayout()
        hdr = QLabel("AURORA")
        hdr.setStyleSheet(
            f"font-size: 18px; font-weight: 700; letter-spacing: 3px; color: {ACCENT};")
        top.addWidget(hdr)
        top.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search title, artist, album...   (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(lambda _: self.search_timer.start())
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.search)
        esc.setContext(Qt.ShortcutContext.WidgetShortcut)
        esc.activated.connect(self._leave_search)
        top.addWidget(self.search)
        main_layout.addLayout(top)
        main_layout.addSpacing(12)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # sidebar
        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 10, 0)
        lbl = QLabel("LIBRARY & PLAYLISTS")
        lbl.setObjectName("section")
        lbl.setContentsMargins(10, 0, 0, 0)
        sl.addWidget(lbl)
        self.sidebar = QListWidget()
        self.sidebar.currentRowChanged.connect(lambda _: self._refresh_table())
        self.sidebar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sidebar.customContextMenuRequested.connect(self._show_sidebar_menu)
        sl.addWidget(self.sidebar)
        btn_new = QPushButton("+  New Playlist")
        btn_new.clicked.connect(self.create_playlist_with_import)
        sl.addWidget(btn_new)
        self.splitter.addWidget(side)

        # table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["TITLE", "ARTIST", "ALBUM", "TIME"])
        hh = self.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col in (0, 1, 2):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 80)
        hh.setSortIndicatorShown(True)
        hh.setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        hh.setSectionsClickable(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setShowGrid(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.itemActivated.connect(self._on_table_activated)   # double-click or Enter
        dele = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.table)
        dele.setContext(Qt.ShortcutContext.WidgetShortcut)
        dele.activated.connect(self._remove_selected)
        self.splitter.addWidget(self.table)

        # right panel: cover, spectrum, mixer
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(15, 0, 0, 0)
        self.cover = CoverArt()
        rl.addWidget(self.cover, stretch=3)

        lbl_sp = QLabel("SPECTRUM")
        lbl_sp.setObjectName("section")
        rl.addWidget(lbl_sp)
        self.visualizer = SpectrumAnalyzer()
        rl.addWidget(self.visualizer, stretch=1)

        lbl_mx = QLabel("MIXER")
        lbl_mx.setObjectName("section")
        rl.addWidget(lbl_mx)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.valueChanged.connect(self.set_vol)
        self.lbl_vol = QLabel("70%")
        self.lbl_vol.setMinimumWidth(42)
        self.lbl_vol.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(QLabel("VOL"), 0, 0)
        grid.addWidget(self.vol_slider, 0, 1)
        grid.addWidget(self.lbl_vol, 0, 2)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(self.set_speed)
        self.lbl_speed_val = QLabel("1.00x")
        self.lbl_speed_val.setMinimumWidth(42)
        self.lbl_speed_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(QLabel("SPD"), 1, 0)
        grid.addWidget(self.speed_slider, 1, 1)
        grid.addWidget(self.lbl_speed_val, 1, 2)
        btn_reset = QPushButton("Reset speed")
        btn_reset.clicked.connect(lambda: self.speed_slider.setValue(100))
        grid.addWidget(btn_reset, 2, 1)
        rl.addLayout(grid)
        self.splitter.addWidget(right)

        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 6)
        self.splitter.setStretchFactor(2, 3)
        main_layout.addWidget(self.splitter, stretch=1)
        main_layout.addSpacing(12)

        # player bar
        bar = QFrame()
        bar.setObjectName("playerBar")
        bl = QVBoxLayout(bar)
        bl.setContentsMargins(15, 10, 15, 10)

        prog = QHBoxLayout()
        self.time_cur = QLabel("0:00")
        self.time_cur.setStyleSheet("color: #707075; font-size: 12px;")
        self.progress = SeekSlider(Qt.Orientation.Horizontal)
        self.progress.sliderPressed.connect(self._on_slider_pressed)
        self.progress.sliderMoved.connect(lambda v: self.time_cur.setText(fmt_time(v / 1000)))
        self.progress.sliderReleased.connect(self._on_seek)
        self.progress.seekRequested.connect(self._seek_to)
        self.time_tot = QLabel("0:00")
        self.time_tot.setStyleSheet("color: #707075; font-size: 12px;")
        prog.addWidget(self.time_cur)
        prog.addWidget(self.progress)
        prog.addWidget(self.time_tot)
        bl.addLayout(prog)

        ctrl = QHBoxLayout()

        info = QVBoxLayout()
        info.setSpacing(0)
        self.lbl_title = QLabel("Ready to play")
        self.lbl_title.setStyleSheet("font-weight: 600; font-size: 14px; color: #ffffff;")
        self.lbl_artist = QLabel("")
        self.lbl_artist.setStyleSheet("color: #a0a0a5; font-size: 12px;")
        for lab in (self.lbl_title, self.lbl_artist):
            lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            info.addWidget(lab)
        info_w = QWidget()
        info_w.setLayout(info)
        info_w.setStyleSheet("background: transparent;")
        ctrl.addWidget(info_w, stretch=1)

        b_prev = QPushButton()
        b_prev.setObjectName("transportBtn")
        b_prev.setIcon(transport_icon("prev"))
        b_prev.setIconSize(QSize(20, 20))
        b_prev.setToolTip("Previous  (Ctrl+Left)")
        b_prev.clicked.connect(self.prev)

        self.btn_play = QPushButton()
        self.btn_play.setObjectName("playBtn")
        self.btn_play.setIconSize(QSize(22, 22))
        self.btn_play.setToolTip("Play / Pause  (Space)")
        self.btn_play.clicked.connect(self.toggle_play)
        self.icon_play = transport_icon("play", "#0b0b0e")
        self.icon_pause = transport_icon("pause", "#0b0b0e")
        self.btn_play.setIcon(self.icon_play)

        b_next = QPushButton()
        b_next.setObjectName("transportBtn")
        b_next.setIcon(transport_icon("next"))
        b_next.setIconSize(QSize(20, 20))
        b_next.setToolTip("Next  (Ctrl+Right)")
        b_next.clicked.connect(self.next)

        for b in (b_prev, self.btn_play, b_next):
            ctrl.addWidget(b)

        right_box = QHBoxLayout()
        right_box.addStretch()
        self.btn_shuffle = QPushButton("Shuffle")
        self.btn_shuffle.setCheckable(True)
        self.btn_shuffle.setToolTip("Random order")
        self.btn_repeat = QPushButton("Repeat")
        self.btn_repeat.setCheckable(True)
        self.btn_repeat.setToolTip("Repeat current track")
        right_box.addWidget(self.btn_shuffle)
        right_box.addWidget(self.btn_repeat)
        right_w = QWidget()
        right_w.setLayout(right_box)
        right_w.setStyleSheet("background: transparent;")
        ctrl.addWidget(right_w, stretch=1)
        bl.addLayout(ctrl)
        main_layout.addWidget(bar)

        self.lbl_stats = QLabel("")
        self.statusBar().addPermanentWidget(self.lbl_stats)

    def _setup_menu(self):
        mb = self.menuBar()

        def act(menu, text, slot, shortcut=None):
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(shortcut)
            a.triggered.connect(slot)
            menu.addAction(a)
            return a

        fm = mb.addMenu("File")
        act(fm, "Open Tracks...", self.open_files, "Ctrl+O")
        act(fm, "Add Folder...", self.add_folder, "Ctrl+Shift+O")
        fm.addSeparator()
        act(fm, "Remove Offline Tracks", self.remove_offline)
        fm.addSeparator()
        act(fm, "Quit", self.close, "Ctrl+Q")

        pm = mb.addMenu("Playback")
        act(pm, "Play / Pause", self.toggle_play, "Space")
        act(pm, "Next", self.next, "Ctrl+Right")
        act(pm, "Previous", self.prev, "Ctrl+Left")
        pm.addSeparator()
        act(pm, "Seek +5 s", lambda: self._seek_by(5000), "Alt+Right")
        act(pm, "Seek -5 s", lambda: self._seek_by(-5000), "Alt+Left")
        pm.addSeparator()
        act(pm, "Volume Up", lambda: self.vol_slider.setValue(self.vol_slider.value() + 5), "Ctrl+Up")
        act(pm, "Volume Down", lambda: self.vol_slider.setValue(self.vol_slider.value() - 5), "Ctrl+Down")
        act(pm, "Mute", self.toggle_mute, "Ctrl+M")

        em = mb.addMenu("Library")
        act(em, "Find...", lambda: (self.search.setFocus(), self.search.selectAll()), "Ctrl+F")

    def _leave_search(self):
        self.search.clear()
        self.table.setFocus()

    # ---- sidebar ---------------------------------------------------------
    def _load_sidebar(self, select_id=0):
        self.sidebar.blockSignals(True)
        self.sidebar.clear()
        it_all = QListWidgetItem("All Tracks")
        it_all.setData(Qt.ItemDataRole.UserRole, 0)
        self.sidebar.addItem(it_all)
        row_to_select = 0
        for pl_id, name in self.conn.execute("SELECT id, name FROM playlists ORDER BY LOWER(name)"):
            it = QListWidgetItem(name)
            it.setData(Qt.ItemDataRole.UserRole, pl_id)
            self.sidebar.addItem(it)
            if pl_id == select_id:
                row_to_select = self.sidebar.count() - 1
        self.sidebar.blockSignals(False)
        self.sidebar.setCurrentRow(row_to_select)
        self._refresh_table()

    def _current_pl_id(self):
        item = self.sidebar.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else 0

    def _show_sidebar_menu(self, pos):
        item = self.sidebar.itemAt(pos)
        if not item or item.data(Qt.ItemDataRole.UserRole) == 0:
            return
        pl_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("Rename...").triggered.connect(lambda: self._rename_playlist(pl_id, item.text()))
        menu.addAction("Add tracks...").triggered.connect(lambda: (self.sidebar.setCurrentItem(item), self.open_files()))
        menu.addSeparator()
        menu.addAction("Delete playlist").triggered.connect(lambda: self._delete_playlist(pl_id, item.text()))
        menu.exec(self.sidebar.viewport().mapToGlobal(pos))

    def _rename_playlist(self, pl_id, old):
        name, ok = QInputDialog.getText(self, "Rename Playlist", "New name:", text=old)
        if ok and name.strip():
            try:
                self.conn.execute("UPDATE playlists SET name=? WHERE id=?", (name.strip(), pl_id))
                self.conn.commit()
                self._load_sidebar(pl_id)
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Error", "A playlist with that name already exists.")

    def _delete_playlist(self, pl_id, name):
        if QMessageBox.question(self, "Delete playlist",
                                f"Delete playlist '{name}'? Your audio files are not touched.") \
                == QMessageBox.StandardButton.Yes:
            self.conn.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (pl_id,))
            self.conn.execute("DELETE FROM playlists WHERE id=?", (pl_id,))
            self.conn.commit()
            self._load_sidebar()

    def create_playlist_with_import(self):
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist Name:")
        if not (ok and name.strip()):
            return
        try:
            cur = self.conn.execute("INSERT INTO playlists (name) VALUES (?)", (name.strip(),))
            self.conn.commit()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Playlist already exists!")
            return
        self._load_sidebar(cur.lastrowid)
        self.open_files()          # optional: choose tracks right away (Cancel to skip)

    # ---- table -----------------------------------------------------------
    def _refresh_table(self):
        item = self.sidebar.currentItem()
        if item is None:
            return
        pl_id = item.data(Qt.ItemDataRole.UserRole)
        q = self.search.text().strip()

        sql = ("SELECT t.id, t.path, t.title, t.artist, COALESCE(t.album,''), t.duration "
               "FROM tracks t")
        where, params = [], []
        if pl_id:
            sql += " JOIN playlist_tracks pt ON pt.track_id = t.id"
            where.append("pt.playlist_id = ?")
            params.append(pl_id)
        if q:
            like = "%" + escape_like(q) + "%"
            where.append("(t.title LIKE ? ESCAPE '\\' OR t.artist LIKE ? ESCAPE '\\' "
                         "OR COALESCE(t.album,'') LIKE ? ESCAPE '\\')")
            params += [like] * 3
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY LOWER(t.artist), LOWER(COALESCE(t.album,'')), LOWER(t.title)"
        rows = self.conn.execute(sql, params).fetchall()

        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        total = 0.0
        gray = QColor(GRAY)
        for r, (tid, path, title, artist, album, dur) in enumerate(rows):
            dur = dur or 0
            total += dur
            offline = not os.path.exists(path)
            shown = title or Path(path).stem
            t_item = SortItem(("[OFFLINE] " if offline else "") + shown, key=shown.lower())
            t_item.setData(Qt.ItemDataRole.UserRole, {"id": tid, "path": path, "offline": offline})
            a_item = SortItem(artist or "Unknown")
            al_item = SortItem(album)
            d_item = SortItem(fmt_time(dur), key=dur)
            d_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for col, it in enumerate((t_item, a_item, al_item, d_item)):
                if offline:
                    it.setForeground(gray)
                self.table.setItem(r, col, it)
        self.table.setSortingEnabled(True)     # re-applies the header's sort indicator
        self.table.setUpdatesEnabled(True)
        self._mark_current()
        self.lbl_stats.setText(f"{len(rows)} tracks  \u00b7  {fmt_long(total)}")

    def _mark_current(self):
        accent = QColor(ACCENT)
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            data = it.data(Qt.ItemDataRole.UserRole)
            playing = data["path"] == self.current_path
            f = it.font()
            f.setBold(playing)
            it.setFont(f)
            if playing:
                it.setForeground(accent)
            elif data["offline"]:
                it.setForeground(QColor(GRAY))
            else:
                it.setData(Qt.ItemDataRole.ForegroundRole, None)

    def _queue(self):
        """Paths in the order currently shown (respects search and column sorting)."""
        return [self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)["path"]
                for r in range(self.table.rowCount())]

    def _selected_tracks(self):
        rows = sorted({i.row() for i in self.table.selectedItems()})
        return [self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows]

    def _on_table_activated(self, item):
        self.play(self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)["path"])

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        if not self.table.item(item.row(), 0).isSelected():
            self.table.clearSelection()
            self.table.selectRow(item.row())
        tracks = self._selected_tracks()
        ids = [t["id"] for t in tracks]

        menu = QMenu(self)
        menu.addAction("Play").triggered.connect(lambda: self.play(tracks[0]["path"]))
        add_menu = menu.addMenu("Add to playlist")
        playlists = self.conn.execute("SELECT id, name FROM playlists ORDER BY LOWER(name)").fetchall()
        if not playlists:
            add_menu.addAction("No playlists available").setEnabled(False)
        for pl_id, pl_name in playlists:
            add_menu.addAction(pl_name).triggered.connect(
                lambda checked=False, pid=pl_id: self._add_to_playlist(pid, ids))

        cur_pl = self._current_pl_id()
        if cur_pl:
            menu.addAction("Remove from playlist").triggered.connect(
                lambda: self._remove_from_playlist(cur_pl, ids))
        menu.addSeparator()
        menu.addAction("Show in folder").triggered.connect(
            lambda: subprocess.Popen(["xdg-open", os.path.dirname(tracks[0]["path"])],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        menu.addAction("Remove from library").triggered.connect(lambda: self._remove_from_library(ids))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _remove_selected(self):
        ids = [t["id"] for t in self._selected_tracks()]
        if not ids:
            return
        pl = self._current_pl_id()
        if pl:
            self._remove_from_playlist(pl, ids)
        else:
            self._remove_from_library(ids)

    def _add_to_playlist(self, pl_id, track_ids):
        self.conn.executemany("INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id) VALUES (?, ?)",
                              [(pl_id, t) for t in track_ids])
        self.conn.commit()
        self.statusBar().showMessage(f"Added {len(track_ids)} track(s) to playlist", 3000)

    def _remove_from_playlist(self, pl_id, track_ids):
        self.conn.executemany("DELETE FROM playlist_tracks WHERE playlist_id=? AND track_id=?",
                              [(pl_id, t) for t in track_ids])
        self.conn.commit()
        self._refresh_table()

    def _remove_from_library(self, track_ids):
        self.conn.executemany("DELETE FROM playlist_tracks WHERE track_id=?", [(t,) for t in track_ids])
        self.conn.executemany("DELETE FROM tracks WHERE id=?", [(t,) for t in track_ids])
        self.conn.commit()
        self._refresh_table()
        self.statusBar().showMessage("Removed from library (files untouched)", 3000)

    def remove_offline(self):
        rows = self.conn.execute("SELECT id, path FROM tracks").fetchall()
        gone = [tid for tid, p in rows if not os.path.exists(p)]
        if not gone:
            self.statusBar().showMessage("No offline tracks", 3000)
            return
        if QMessageBox.question(self, "Remove offline tracks",
                                f"Remove {len(gone)} missing track(s) from the library?") \
                == QMessageBox.StandardButton.Yes:
            self._remove_from_library(gone)

    # ---- importing -------------------------------------------------------
    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open Audio Files", self.last_dir, AUDIO_FILTER)
        if files:
            self.last_dir = str(Path(files[0]).parent)
            self._import_paths(files)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder", self.last_dir)
        if folder:
            self.last_dir = folder
            self._import_paths([folder])

    def _import_paths(self, paths):
        files = expand_paths(paths)
        if not files:
            self.statusBar().showMessage("No supported audio files found", 4000)
            return
        if self.scan_worker is not None:
            self.statusBar().showMessage("An import is already running", 4000)
            return
        self._import_target = self._current_pl_id()
        self._import_count = 0

        dlg = QProgressDialog("Importing tracks...", "Cancel", 0, len(files), self)
        dlg.setWindowTitle("Aurora")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(400)
        dlg.setAutoClose(True)
        self.scan_dialog = dlg

        worker = ScanWorker(files, self)
        worker.scanned.connect(self._on_track_scanned)
        worker.progress.connect(dlg.setValue)
        worker.finished.connect(self._on_scan_finished)
        dlg.canceled.connect(worker.requestInterruption)
        self.scan_worker = worker
        worker.start()

    def _on_track_scanned(self, meta):
        tid = self._upsert_track(meta)
        if tid and self._import_target:
            self.conn.execute("INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id) VALUES (?, ?)",
                              (self._import_target, tid))
        self._import_count += 1

    def _on_scan_finished(self):
        self.conn.commit()
        if self.scan_dialog:
            self.scan_dialog.reset()
            self.scan_dialog.deleteLater()
            self.scan_dialog = None
        if self.scan_worker:
            self.scan_worker.deleteLater()
            self.scan_worker = None
        self._refresh_table()
        self.statusBar().showMessage(f"Imported {self._import_count} track(s)", 5000)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self._import_paths(paths)

    # ---- playback --------------------------------------------------------
    def play(self, path, record=True, silent=False):
        if not os.path.exists(path):
            if not silent:
                QMessageBox.warning(self, "Offline", "Track is offline.")
            return False
        if not self.player:
            QMessageBox.information(self, "Aurora", "Qt Multimedia is not available.")
            return False

        if record and self.current_path and self.current_path != path:
            self.history.append(self.current_path)
            del self.history[:-200]
        self.current_path = path

        row = self.conn.execute("SELECT title, artist, COALESCE(album,'') FROM tracks WHERE path=?",
                                (path,)).fetchone()
        title, artist, album = row if row else (Path(path).stem, "Unknown", "")
        self.lbl_title.setText(title)                      # plain text: no HTML injection from tags
        self.lbl_artist.setText(artist + (f"  \u2014  {album}" if album else ""))
        self.setWindowTitle(f"{title} \u2014 {artist}  \u00b7  Aurora")
        self.cover.set_pixmap(read_cover(path))

        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self._mark_current()

        if not self.isActiveWindow() and shutil.which("notify-send"):
            icon = str(ICON_PATH) if ICON_PATH.exists() else "multimedia-audio-player"
            try:
                subprocess.Popen(["notify-send", "-a", "Aurora", "-i", icon, title, artist],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        return True

    def toggle_play(self):
        if not self.player:
            return
        if not self.player.source().isValid():
            q = self._queue()
            sel = self._selected_tracks()
            if sel:
                self.play(sel[0]["path"])
            elif q:
                self.play(q[0])
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _advance(self, step):
        q = self._queue()
        if not q:
            return
        cur = self.current_path
        if self.btn_shuffle.isChecked() and len(q) > 1 and step > 0:
            order = [p for p in q if p != cur]
            random.shuffle(order)
        else:
            i = q.index(cur) if cur in q else (-1 if step > 0 else 0)
            order = [q[(i + step * k) % len(q)] for k in range(1, len(q) + 1)]
        for p in order:                       # skip offline tracks silently
            if self.play(p, silent=True):
                return
        self.statusBar().showMessage("No playable tracks in this view", 4000)

    def next(self):
        self._advance(+1)

    def prev(self):
        if self.player and self.player.position() > 3000:
            self.player.setPosition(0)        # like most players: first rewind the track
            return
        while self.history:
            p = self.history.pop()
            if self.play(p, record=False, silent=True):
                return
        self._advance(-1)

    def stop(self):
        if self.player:
            self.player.stop()
            self.progress.setValue(0)
            self.time_cur.setText("0:00")

    def set_vol(self, v):
        self.lbl_vol.setText(f"{v}%")
        if self.audio:
            self.audio.setVolume((v / 100.0) ** 2)    # quadratic: closer to perceived loudness

    def toggle_mute(self):
        if self.audio:
            muted = not self.audio.isMuted()
            self.audio.setMuted(muted)
            self.statusBar().showMessage("Muted" if muted else "Unmuted", 2000)

    def set_speed(self, v):
        rate = v / 100.0
        self.lbl_speed_val.setText(f"{rate:.2f}x")
        if self.player:
            self.player.setPlaybackRate(rate)

    def _seek_by(self, ms):
        if self.player and self.player.duration() > 0:
            self._seek_to(max(0, min(self.player.duration(), self.player.position() + ms)))

    def _seek_to(self, ms):
        if self.player:
            self.player.setPosition(int(ms))

    def _on_slider_pressed(self):
        self.is_seeking = True

    def _on_seek(self):
        self._seek_to(self.progress.value())
        self.is_seeking = False

    def _on_duration_changed(self, dur):
        self.progress.setMaximum(max(0, dur))
        self.time_tot.setText(fmt_time(dur / 1000))

    def _on_position_changed(self, pos):
        if not self.is_seeking:
            self.progress.setValue(pos)
            self.time_cur.setText(fmt_time(pos / 1000))

    def _on_state_changed(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.setIcon(self.icon_pause if playing else self.icon_play)
        self.visualizer.set_playing(playing)

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.btn_repeat.isChecked():
                self.player.setPosition(0)
                self.player.play()
            else:
                self.next()

    def _on_player_error(self, error, message):
        if message:
            self.statusBar().showMessage(f"Playback error: {message}", 6000)


# --------------------------------------------------------------------------
# Desktop integration / entry point
# --------------------------------------------------------------------------
def setup_desktop_integration():
    desktop_dir = Path.home() / ".local" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = desktop_dir / "aurora.desktop"

    icon = str(ICON_PATH) if ICON_PATH.exists() else "multimedia-audio-player"
    content = f"""[Desktop Entry]
Name=Aurora
Comment=Aurora Music Player
Exec="{sys.executable}" "{os.path.abspath(__file__)}" %F
Icon={icon}
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;
MimeType=audio/mpeg;audio/x-flac;audio/flac;audio/ogg;audio/x-vorbis+ogg;audio/x-opus+ogg;audio/mp4;audio/x-wav;audio/wav;
"""
    try:
        # rewrite if the script was moved or the icon appeared since last run
        if not desktop_file.exists() or desktop_file.read_text() != content:
            desktop_file.write_text(content)
            subprocess.run(["update-desktop-database", str(desktop_dir)],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def apply_dark_palette(app):
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: "#0b0b0e", QPalette.ColorRole.WindowText: "#e2e2e5",
        QPalette.ColorRole.Base: "#0b0b0e", QPalette.ColorRole.AlternateBase: "#15151a",
        QPalette.ColorRole.Text: "#e2e2e5", QPalette.ColorRole.Button: "#15151a",
        QPalette.ColorRole.ButtonText: "#e2e2e5", QPalette.ColorRole.ToolTipBase: "#15151a",
        QPalette.ColorRole.ToolTipText: "#e2e2e5", QPalette.ColorRole.Highlight: ACCENT2,
        QPalette.ColorRole.HighlightedText: "#ffffff",
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    app.setPalette(pal)


def main():
    setup_desktop_integration()

    files = [os.path.abspath(f) for f in sys.argv[1:] if os.path.exists(f)]

    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_socket.bind(SOCKET_NAME)
    except OSError:
        # Aurora is already running: hand over absolute paths (our CWD may differ) and exit
        try:
            lock_socket.sendto("\n".join(files).encode("utf-8"), SOCKET_NAME)
        except OSError:
            pass
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setDesktopFileName("aurora.desktop")
    app.setStyle("Fusion")
    apply_dark_palette(app)
    app.setStyleSheet(STYLESHEET)        # app-wide: menus, dialogs and tooltips match too
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    win = Aurora()
    win.setup_ipc(lock_socket)
    win.show()
    if files:
        win.open_external_files(files)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
