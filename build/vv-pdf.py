#!/usr/bin/env python3
"""
VaeVictis PDF Tool - offline PDF viewer and page editor (PyMuPDF + PyQt6)
Privacy: zero network access, 100% offline
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

try:
    import pymupdf as fitz          # PyMuPDF >= 1.24
except ImportError:                  # older packaging
    import fitz

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QFileDialog,
    QScrollArea, QMessageBox, QListWidget, QListWidgetItem, QSplitter,
    QSpinBox, QLineEdit, QToolBar, QInputDialog, QProgressDialog, QSizePolicy,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QTimer, QSize, QSettings, pyqtSignal
from PyQt6.QtGui import (
    QAction, QColor, QIcon, QImage, QKeySequence, QPainter, QPalette, QPixmap,
    QShortcut,
)

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
ACCENT = "#35f0a1"          # mint green (the original cyber-green, softened)
BASE_SCALE = 96 / 72        # zoom 100% ~ real size on a 96 dpi screen
PAD = 24                    # margin around the page
MAX_PIXELS = 36_000_000     # cap on rendered bitmap size (protects RAM at high zoom)
THUMB_W, THUMB_H = 120, 160
UNDO_MAX = 15
UNDO_BYTES = 400 * 1024 * 1024

STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0b0b0e;
    color: #e2e2e5;
    font-family: system-ui, sans-serif;
    font-size: 13px;
}
QToolTip { background-color: #15151a; color: #e2e2e5; border: 1px solid #2a2a32; padding: 4px; }
QMenuBar { background-color: #0b0b0e; color: #a0a0a5; }
QMenuBar::item { padding: 6px 10px; background: transparent; border-radius: 6px; }
QMenuBar::item:selected { background-color: #1c1c22; color: #ffffff; }
QMenu { background-color: #15151a; color: #e2e2e5; border: 1px solid #222228; padding: 4px; }
QMenu::item { padding: 6px 28px 6px 24px; border-radius: 4px; }
QMenu::item:selected { background-color: #2a2a32; }
QMenu::item:disabled { color: #505055; }
QMenu::separator { height: 1px; background: #222228; margin: 4px 8px; }
QToolBar { background: #0b0b0e; border: none; spacing: 4px; padding: 4px 6px; }
QToolBar::separator { background: #222228; width: 1px; margin: 4px 6px; }
QToolButton {
    background: transparent; color: #a0a0a5; border: none; border-radius: 8px;
    padding: 6px 10px; font-weight: 600;
}
QToolButton:hover { background-color: #1c1c22; color: #ffffff; }
QToolButton:pressed { background-color: #2a2a32; }
QToolButton:checked { background-color: #1c1c22; color: %ACCENT%; }
QToolButton:disabled { color: #3a3a42; }
QStatusBar { background-color: #0b0b0e; color: #707075; font-size: 12px; }
QStatusBar::item { border: none; }
QLineEdit, QSpinBox {
    background-color: #15151a; border: 1px solid #222228; border-radius: 14px;
    padding: 5px 12px; color: #ffffff;
}
QLineEdit:focus, QSpinBox:focus { border: 1px solid %ACCENT%; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; border: none; }
QSplitter::handle { background-color: #0b0b0e; }
QScrollArea { border: none; background-color: #15151a; }
QListWidget { background-color: #0b0b0e; border: none; outline: none; }
QListWidget::item { padding: 6px; margin: 2px 6px; border-radius: 8px; color: #a0a0a5; }
QListWidget::item:selected { background-color: #1c1c22; color: #ffffff; border-left: 3px solid %ACCENT%; }
QListWidget::item:hover:!selected { background-color: #15151a; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #2a2a32; border-radius: 6px; min-height: 30px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: #3a3a42; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #2a2a32; border-radius: 6px; min-width: 30px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background: #3a3a42; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QLabel#zoomLabel { color: #a0a0a5; font-weight: 600; min-width: 48px; }
QLabel#empty { color: #505055; font-size: 16px; }
""".replace("%ACCENT%", ACCENT)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def ranges(pages):
    """[0,1,2,5,6] -> [(0,2),(5,6)] : contiguous runs, so insert_pdf is called few times."""
    out = []
    for p in sorted(set(pages)):
        if out and p == out[-1][1] + 1:
            out[-1] = (out[-1][0], p)
        else:
            out.append((p, p))
    return out


def pix_to_qimage(pix):
    """PyMuPDF pixmap (RGB, no alpha) -> detached QImage."""
    return QImage(pix.samples, pix.width, pix.height, pix.stride,
                  QImage.Format.Format_RGB888).copy()


# --------------------------------------------------------------------------
# Widgets
# --------------------------------------------------------------------------
class PdfScrollArea(QScrollArea):
    """Scroll area with Ctrl+wheel zoom, drag-to-pan and page flipping at the edges."""
    zoomRequested = pyqtSignal(float)
    pageStep = pyqtSignal(int)
    resized = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag = None
        self._cool = QTimer(self)
        self._cool.setSingleShot(True)
        self._cool.setInterval(220)
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)

    def wheelEvent(self, e):
        dy = e.angleDelta().y()
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if dy:
                self.zoomRequested.emit(1.15 if dy > 0 else 1 / 1.15)
            e.accept()
            return
        sb = self.verticalScrollBar()
        if dy < 0 and sb.value() >= sb.maximum():
            if not self._cool.isActive():
                self.pageStep.emit(+1)
                self._cool.start()
            e.accept()
            return
        if dy > 0 and sb.value() <= sb.minimum():
            if not self._cool.isActive():
                self.pageStep.emit(-1)
                self._cool.start()
            e.accept()
            return
        super().wheelEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            d = e.position().toPoint() - self._drag
            self._drag = e.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag = None
        self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.resized.emit()


class ThumbList(QListWidget):
    """Page thumbnails; drag & drop reorders pages."""
    reordered = pyqtSignal()

    def dropEvent(self, e):
        super().dropEvent(e)
        self.reordered.emit()


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------
class VaeVictisPDF(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(1040, 640)
        self.setAcceptDrops(True)
        self.settings = QSettings("VaeVictis", "PDFTool")
        self.last_dir = str(self.settings.value("last_dir", str(Path.home())))

        # document state
        self.doc = None
        self.path = None
        self.password = None
        self.current = 0
        self.dirty = False
        self.undo_stack = []          # [(bytes, page_index)]
        self.undo_bytes = 0

        # view state
        self.zoom = 1.0
        self.fit = "width"            # "width" | "page" | None (manual zoom)
        self.invert = self.settings.value("invert", False, type=bool)
        self._scale_px = 1.0          # last render scale (device px per PDF point)
        self._sync = False            # guards thumbnail <-> page sync

        # search state
        self.hits = []                # [(page, fitz.Rect in rotated page coords)]
        self.hit_idx = -1

        # thumbnails (lazy rendering)
        self.thumb_gen = 0
        self.thumb_next = 0
        self.thumb_timer = QTimer(self)
        self.thumb_timer.setInterval(0)
        self.thumb_timer.timeout.connect(self._thumb_tick)
        ph = QPixmap(THUMB_W, THUMB_H)
        ph.fill(QColor("#15151a"))
        self.thumb_placeholder = QIcon(ph)
        self.thumb_placeholder.addPixmap(ph, QIcon.Mode.Selected)

        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.setInterval(90)
        self.fit_timer.timeout.connect(self._on_resized)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(450)
        self.search_timer.timeout.connect(self._run_search)

        self._build_actions()
        self._build_toolbars()
        self._build_menu()
        self._build_ui()
        self._restore_settings()
        self._update_ui()
        self.render_page()

    # ---- actions ----------------------------------------------------------
    def _act(self, text, slot, shortcut=None, tip=None):
        a = QAction(text, self)
        if shortcut:
            keys = shortcut if isinstance(shortcut, (list, tuple)) else [shortcut]
            a.setShortcuts([QKeySequence(k) for k in keys])
        label = tip or text.replace("&", "")
        if shortcut:
            first = shortcut[0] if isinstance(shortcut, (list, tuple)) else shortcut
            label += f"  ({first})"
        a.setToolTip(label)
        a.triggered.connect(lambda checked=False: slot())
        return a

    def _build_actions(self):
        A = self._act
        self.a_open = A("Open", self.open_dialog, "Ctrl+O", "Open PDF")
        self.a_save = A("Save", self.save, "Ctrl+S", "Save changes")
        self.a_save_as = A("Save As...", self.save_as, "Ctrl+Shift+S")
        self.a_png = A("Export Page as PNG...", self.export_png)
        self.a_split = A("Split into Single Pages...", self.split_pages)
        self.a_props = A("Document Properties", self.show_properties, "Ctrl+I")
        self.a_quit = A("Quit", self.close, "Ctrl+Q")

        self.a_undo = A("Undo", self.undo, "Ctrl+Z")
        self.a_find = A("Find...", self.focus_search, "Ctrl+F")
        self.a_find_next = A("Find Next", lambda: self._step_hit(+1), "F3")
        self.a_find_prev = A("Find Previous", lambda: self._step_hit(-1), "Shift+F3")

        self.a_rot_l = A("Rotate L", lambda: self.rotate(-90), "Ctrl+L", "Rotate selected pages left")
        self.a_rot_r = A("Rotate R", lambda: self.rotate(+90), "Ctrl+R", "Rotate selected pages right")
        self.a_up = A("Move Up", lambda: self.move_pages(-1), "Ctrl+Shift+Up", "Move selected pages up")
        self.a_down = A("Move Down", lambda: self.move_pages(+1), "Ctrl+Shift+Down", "Move selected pages down")
        self.a_delete = A("Delete", self.delete_pages, None, "Delete selected pages (Del in thumbnails)")
        self.a_extract = A("Extract...", self.extract_pages, "Ctrl+E", "Save selected pages as a new PDF")
        self.a_insert = A("Insert PDF...", lambda: self.merge_pdfs(after_current=True), None,
                          "Insert PDF(s) after the current page")
        self.a_append = A("Append PDF...", lambda: self.merge_pdfs(after_current=False), None,
                          "Append PDF(s) at the end")

        self.a_prev = A("Prev", lambda: self.step_page(-1), "PgUp", "Previous page")
        self.a_next = A("Next", lambda: self.step_page(+1), "PgDown", "Next page")
        self.a_first = A("First Page", lambda: self.goto(0), "Home")
        self.a_last = A("Last Page", lambda: self.goto(10 ** 9), "End")
        self.a_zoom_in = A("Zoom +", lambda: self.zoom_by(1.15), ["Ctrl++", "Ctrl+="], "Zoom in")
        self.a_zoom_out = A("Zoom -", lambda: self.zoom_by(1 / 1.15), "Ctrl+-", "Zoom out")
        self.a_actual = A("Actual Size", lambda: self.set_zoom(1.0), "Ctrl+0")
        self.a_fit_w = A("Fit Width", lambda: self.set_fit("width"), "Ctrl+1")
        self.a_fit_p = A("Fit Page", lambda: self.set_fit("page"), "Ctrl+2")

        self.a_invert = QAction("Night Mode (invert colors)", self)
        self.a_invert.setCheckable(True)
        self.a_invert.setChecked(self.invert)
        self.a_invert.setShortcut(QKeySequence("Ctrl+D"))
        self.a_invert.toggled.connect(self._toggle_invert)

        self.a_thumbs = QAction("Show Thumbnails", self)
        self.a_thumbs.setCheckable(True)
        self.a_thumbs.setChecked(True)
        self.a_thumbs.setShortcut(QKeySequence("F9"))
        self.a_thumbs.toggled.connect(lambda on: self.thumbs.setVisible(on))

    def _build_toolbars(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)
        tb.addAction(self.a_open)
        tb.addSeparator()
        tb.addAction(self.a_prev)
        self.page_spin = QSpinBox()
        self.page_spin.setKeyboardTracking(False)
        self.page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_spin.setFixedWidth(56)
        self.page_spin.valueChanged.connect(lambda v: self.goto(v - 1))
        tb.addWidget(self.page_spin)
        self.page_total = QLabel("/ 0")
        self.page_total.setMinimumWidth(40)
        tb.addWidget(self.page_total)
        tb.addAction(self.a_next)
        tb.addSeparator()
        tb.addAction(self.a_zoom_out)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("zoomLabel")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb.addWidget(self.zoom_label)
        tb.addAction(self.a_zoom_in)
        tb.addAction(self.a_fit_w)
        tb.addAction(self.a_fit_p)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find in document...   (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(lambda _: self.search_timer.start())
        self.search.returnPressed.connect(lambda: self._step_hit(+1))
        sh = QShortcut(QKeySequence("Shift+Return"), self.search)
        sh.setContext(Qt.ShortcutContext.WidgetShortcut)
        sh.activated.connect(lambda: self._step_hit(-1))
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.search)
        esc.setContext(Qt.ShortcutContext.WidgetShortcut)
        esc.activated.connect(self._leave_search)
        tb.addWidget(self.search)

        self.addToolBarBreak()
        tb2 = QToolBar("Pages")
        tb2.setMovable(False)
        self.addToolBar(tb2)
        for a in (self.a_save, self.a_undo):
            tb2.addAction(a)
        tb2.addSeparator()
        for a in (self.a_rot_l, self.a_rot_r, self.a_up, self.a_down, self.a_delete):
            tb2.addAction(a)
        tb2.addSeparator()
        for a in (self.a_extract, self.a_insert, self.a_append):
            tb2.addAction(a)

    def _build_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        for a in (self.a_open, self.a_save, self.a_save_as):
            fm.addAction(a)
        fm.addSeparator()
        for a in (self.a_png, self.a_split, self.a_props):
            fm.addAction(a)
        fm.addSeparator()
        fm.addAction(self.a_quit)

        em = mb.addMenu("Edit")
        for a in (self.a_undo,):
            em.addAction(a)
        em.addSeparator()
        for a in (self.a_find, self.a_find_next, self.a_find_prev):
            em.addAction(a)

        pm = mb.addMenu("Pages")
        for a in (self.a_rot_l, self.a_rot_r):
            pm.addAction(a)
        pm.addSeparator()
        for a in (self.a_up, self.a_down, self.a_delete):
            pm.addAction(a)
        pm.addSeparator()
        for a in (self.a_extract, self.a_insert, self.a_append):
            pm.addAction(a)

        vm = mb.addMenu("View")
        for a in (self.a_prev, self.a_next, self.a_first, self.a_last):
            vm.addAction(a)
        vm.addSeparator()
        for a in (self.a_zoom_in, self.a_zoom_out, self.a_actual, self.a_fit_w, self.a_fit_p):
            vm.addAction(a)
        vm.addSeparator()
        vm.addAction(self.a_invert)
        vm.addAction(self.a_thumbs)

    def _build_ui(self):
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        self.thumbs = ThumbList()
        self.thumbs.setIconSize(QSize(THUMB_W, THUMB_H))
        self.thumbs.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.thumbs.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.thumbs.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.thumbs.setSpacing(2)
        self.thumbs.setMinimumWidth(150)
        self.thumbs.setMaximumWidth(260)
        self.thumbs.currentRowChanged.connect(self._on_thumb_row)
        self.thumbs.reordered.connect(self._on_reordered)
        self.thumbs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.thumbs.customContextMenuRequested.connect(self._thumb_menu)
        dele = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.thumbs)
        dele.setContext(Qt.ShortcutContext.WidgetShortcut)
        dele.activated.connect(self.delete_pages)
        self.splitter.addWidget(self.thumbs)

        self.scroll = PdfScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.zoomRequested.connect(self.zoom_by)
        self.scroll.pageStep.connect(self._wheel_page)
        self.scroll.resized.connect(self.fit_timer.start)
        self.image_label = QLabel()
        self.image_label.setObjectName("empty")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setContentsMargins(PAD, PAD, PAD, PAD)
        self.image_label.setStyleSheet("background: transparent;")
        self.scroll.setWidget(self.image_label)
        self.splitter.addWidget(self.scroll)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([170, 900])

        self.lbl_info = QLabel("")
        self.statusBar().addPermanentWidget(self.lbl_info)
        self.statusBar().showMessage("Drop a PDF on the window or press Ctrl+O", 6000)

    def _restore_settings(self):
        geo = self.settings.value("geometry")
        self.resize(1180, 820)
        if geo is not None:
            self.restoreGeometry(geo)
        st = self.settings.value("splitter")
        if st is not None:
            self.splitter.restoreState(st)
        self.a_thumbs.setChecked(self.settings.value("thumbs", True, type=bool))
        self.thumbs.setVisible(self.a_thumbs.isChecked())

    # ---- state helpers ------------------------------------------------------
    def _selected_pages(self):
        rows = sorted({self.thumbs.row(i) for i in self.thumbs.selectedItems()})
        return rows or ([self.current] if self.doc else [])

    def _update_ui(self):
        has = self.doc is not None
        n = len(self.doc) if has else 0
        for a in (self.a_save_as, self.a_png, self.a_split, self.a_props, self.a_find,
                  self.a_rot_l, self.a_rot_r, self.a_extract, self.a_insert, self.a_append,
                  self.a_first, self.a_last, self.a_zoom_in, self.a_zoom_out, self.a_actual,
                  self.a_fit_w, self.a_fit_p):
            a.setEnabled(has)
        self.a_save.setEnabled(has and (self.dirty or self.path is None))
        self.a_undo.setEnabled(bool(self.undo_stack))
        self.a_delete.setEnabled(has and n > 1)
        self.a_up.setEnabled(has and n > 1)
        self.a_down.setEnabled(has and n > 1)
        self.a_prev.setEnabled(has and self.current > 0)
        self.a_next.setEnabled(has and self.current < n - 1)
        self.a_find_next.setEnabled(has)
        self.a_find_prev.setEnabled(has)
        self.search.setEnabled(has)
        self.page_spin.setEnabled(has)

        self._sync = True
        self.page_spin.setRange(1 if has else 0, max(n, 0))
        self.page_spin.setValue(self.current + 1 if has else 0)
        self._sync = False
        self.page_total.setText(f"/ {n}")

        name = os.path.basename(self.path) if self.path else ("Untitled" if has else "")
        self.setWindowTitle(
            (f"{'* ' if self.dirty else ''}{name}  \u2014  " if has else "") + "VaeVictis PDF Tool")
        if has:
            size = ""
            if self.path and os.path.exists(self.path):
                size = f"  \u00b7  {fmt_size(os.path.getsize(self.path))}"
            self.lbl_info.setText(f"{name}  \u00b7  {n} pages{size}{'  \u00b7  modified' if self.dirty else ''}")
        else:
            self.lbl_info.setText("")

    def _mark_dirty(self):
        self.dirty = True
        self.hits, self.hit_idx = [], -1
        self._update_ui()

    # ---- opening / closing ---------------------------------------------------
    def _confirm_discard(self):
        if not (self.doc and self.dirty):
            return True
        r = QMessageBox.question(
            self, "Unsaved changes", "Save changes before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            return self.save()
        return r == QMessageBox.StandardButton.Discard

    def open_dialog(self):
        if not self._confirm_discard():
            return
        name, _ = QFileDialog.getOpenFileName(self, "Open PDF", self.last_dir, "PDF Files (*.pdf);;All Files (*)")
        if name:
            self.open_path(name)

    def _authenticated_doc(self, path, password=None):
        """Open a PDF, asking for a password when needed. Returns (doc, password) or (None, None)."""
        try:
            doc = fitz.open(path)
        except Exception as e:
            QMessageBox.critical(self, "Cannot open", f"{os.path.basename(path)}\n\n{e}")
            return None, None
        if doc.needs_pass:
            if password is not None and doc.authenticate(password):
                return doc, password
            for _ in range(3):
                pw, ok = QInputDialog.getText(
                    self, "Password required", f"{os.path.basename(path)} is encrypted.\nPassword:",
                    QLineEdit.EchoMode.Password)
                if not ok:
                    doc.close()
                    return None, None
                if doc.authenticate(pw):
                    return doc, pw
            QMessageBox.warning(self, "Wrong password", "Could not unlock the document.")
            doc.close()
            return None, None
        return doc, None

    def open_path(self, path, password=None, keep_page=0, keep_undo=False):
        doc, pw = self._authenticated_doc(path, password)
        if doc is None:
            return False
        if len(doc) == 0:
            QMessageBox.warning(self, "Empty document", "This PDF has no pages.")
            doc.close()
            return False
        if self.doc:
            self.doc.close()
        self.doc, self.path, self.password = doc, os.path.abspath(path), pw
        self.current = max(0, min(keep_page, len(doc) - 1))
        self.dirty = False
        self.hits, self.hit_idx = [], -1
        if not keep_undo:
            self.undo_stack, self.undo_bytes = [], 0
        self.last_dir = os.path.dirname(self.path)
        self._build_thumbs()
        self._update_ui()
        self.render_page(scroll="top")
        return True

    def closeEvent(self, event):
        if not self._confirm_discard():
            event.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
        self.settings.setValue("last_dir", self.last_dir)
        self.settings.setValue("invert", self.invert)
        self.settings.setValue("thumbs", self.a_thumbs.isChecked())
        self.thumb_timer.stop()
        if self.doc:
            self.doc.close()
        super().closeEvent(event)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        pdfs = [u.toLocalFile() for u in e.mimeData().urls()
                if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf")]
        if pdfs and self._confirm_discard():
            self.open_path(pdfs[0])

    # ---- rendering --------------------------------------------------------------
    def _effective_zoom(self, page):
        r = page.rect
        vp = self.scroll.viewport()
        if self.fit == "width":
            z = (vp.width() - 2 * PAD) / (r.width * BASE_SCALE)
        elif self.fit == "page":
            z = min((vp.width() - 2 * PAD) / (r.width * BASE_SCALE),
                    (vp.height() - 2 * PAD) / (r.height * BASE_SCALE))
        else:
            z = self.zoom
        return max(0.1, min(8.0, z))

    def render_page(self, scroll=None):
        """scroll: None (keep relative position) | 'top' | 'bottom' | ('hit', QRectF-like tuple)"""
        if not self.doc:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("Drop a PDF here\nor press Ctrl+O")
            self.zoom_label.setText("\u2014")
            return
        hs, vs = self.scroll.horizontalScrollBar(), self.scroll.verticalScrollBar()
        fx = hs.value() / hs.maximum() if hs.maximum() else 0.0
        fy = vs.value() / vs.maximum() if vs.maximum() else 0.0

        page = self.doc[self.current]
        dpr = self.devicePixelRatioF()
        self.zoom = self._effective_zoom(page)
        scale = self.zoom * BASE_SCALE * dpr
        r = page.rect
        px = (r.width * scale) * (r.height * scale)
        if px > MAX_PIXELS:
            scale *= (MAX_PIXELS / px) ** 0.5
        self._scale_px = scale
        self.zoom_label.setText(f"{self.zoom * 100:.0f}%")

        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        except Exception as e:
            self.image_label.setText(f"Cannot render page {self.current + 1}:\n{e}")
            return
        img = pix_to_qimage(pix)
        if self.invert:
            img.invertPixels()
        self._paint_hits(img, page, scale)
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        self.image_label.setText("")
        self.image_label.setPixmap(pm)
        self._update_ui()

        def apply():
            if scroll == "top":
                vs.setValue(vs.minimum())
            elif scroll == "bottom":
                vs.setValue(vs.maximum())
            elif isinstance(scroll, tuple) and scroll[0] == "hit":
                _, x, y = scroll
                lx = (self.image_label.width() - pm.width() / dpr) / 2 + x
                ly = (self.image_label.height() - pm.height() / dpr) / 2 + y
                self.scroll.ensureVisible(int(lx), int(ly), 60, 140)
            else:
                hs.setValue(int(fx * hs.maximum()))
                vs.setValue(int(fy * vs.maximum()))
        QTimer.singleShot(0, apply)

    def _paint_hits(self, img, page, scale):
        here = [(i, r) for i, (p, r) in enumerate(self.hits) if p == self.current]
        if not here:
            return
        p = QPainter(img)
        rot = page.rotation_matrix
        for i, rect in here:
            rr = fitz.Rect(rect) * rot
            cur = i == self.hit_idx
            p.fillRect(int(rr.x0 * scale) - 1, int(rr.y0 * scale) - 1,
                       int((rr.x1 - rr.x0) * scale) + 2, int((rr.y1 - rr.y0) * scale) + 2,
                       QColor(255, 140, 0, 130) if cur else QColor(255, 235, 0, 90))
        p.end()

    # ---- navigation / zoom -----------------------------------------------------
    def goto(self, n, scroll="top"):
        if not self.doc or self._sync:
            return
        n = max(0, min(int(n), len(self.doc) - 1))
        if n == self.current and scroll != "force":
            return
        self.current = n
        self._sync = True
        self.thumbs.setCurrentRow(n)
        self._sync = False
        self.render_page(scroll="top" if scroll == "force" else scroll)

    def step_page(self, d):
        self.goto(self.current + d)

    def _wheel_page(self, d):
        before = self.current
        self.goto(self.current + d, scroll="top" if d > 0 else "bottom")
        if self.current == before:
            return

    def zoom_by(self, f):
        if not self.doc:
            return
        self.fit = None
        self.zoom = max(0.1, min(8.0, self.zoom * f))
        self.render_page()

    def set_zoom(self, z):
        if self.doc:
            self.fit = None
            self.zoom = z
            self.render_page()

    def set_fit(self, mode):
        if self.doc:
            self.fit = mode
            self.render_page(scroll="top")

    def _on_resized(self):
        if self.doc and self.fit:
            self.render_page()

    def _toggle_invert(self, on):
        self.invert = on
        self._build_thumbs()
        self.render_page()

    # ---- thumbnails ---------------------------------------------------------------
    def _build_thumbs(self):
        self.thumb_gen += 1
        self._sync = True
        self.thumbs.clear()
        if self.doc:
            for i in range(len(self.doc)):
                it = QListWidgetItem(self.thumb_placeholder, str(i + 1))
                it.setData(Qt.ItemDataRole.UserRole, i)
                it.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                self.thumbs.addItem(it)
            self.thumbs.setCurrentRow(self.current)
        self._sync = False
        self.thumb_next = 0
        if self.doc:
            self.thumb_timer.start()

    def _thumb_icon(self, i):
        page = self.doc[i]
        r = page.rect
        s = min(THUMB_W / r.width, THUMB_H / r.height) * self.devicePixelRatioF()
        img = pix_to_qimage(page.get_pixmap(matrix=fitz.Matrix(s, s), alpha=False))
        if self.invert:
            img.invertPixels()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(self.devicePixelRatioF())
        icon = QIcon(pm)
        icon.addPixmap(pm, QIcon.Mode.Selected)      # no grey tint on selected thumbnails
        icon.addPixmap(pm, QIcon.Mode.Active)
        return icon

    def _thumb_tick(self):
        gen = self.thumb_gen
        if not self.doc or self.thumb_next >= len(self.doc):
            self.thumb_timer.stop()
            return
        for _ in range(3):
            i = self.thumb_next
            if i >= len(self.doc) or i >= self.thumbs.count():
                break
            try:
                self.thumbs.item(i).setIcon(self._thumb_icon(i))
            except Exception:
                pass
            self.thumb_next += 1
        if gen != self.thumb_gen:
            return

    def _refresh_thumb(self, i):
        if self.doc and 0 <= i < self.thumbs.count():
            self.thumbs.item(i).setIcon(self._thumb_icon(i))

    def _on_thumb_row(self, row):
        if row >= 0 and not self._sync:
            self.goto(row)

    def _thumb_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        if not self.doc:
            return
        m = QMenu(self)
        for a in (self.a_rot_l, self.a_rot_r, self.a_up, self.a_down, self.a_delete):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_extract)
        m.addAction(self.a_insert)
        m.exec(self.thumbs.viewport().mapToGlobal(pos))

    # ---- undo ------------------------------------------------------------------------
    def _push_undo(self):
        try:
            data = self.doc.tobytes()
        except Exception:
            return
        self.undo_stack.append((data, self.current))
        self.undo_bytes += len(data)
        while self.undo_stack and (len(self.undo_stack) > UNDO_MAX or self.undo_bytes > UNDO_BYTES):
            old, _ = self.undo_stack.pop(0)
            self.undo_bytes -= len(old)

    def undo(self):
        if not self.undo_stack:
            return
        data, page = self.undo_stack.pop()
        self.undo_bytes -= len(data)
        try:
            doc = fitz.open("pdf", data)
            if doc.needs_pass:
                doc.authenticate(self.password or "")
        except Exception as e:
            QMessageBox.warning(self, "Undo failed", str(e))
            return
        self.doc.close()
        self.doc = doc
        self.current = max(0, min(page, len(doc) - 1))
        self._build_thumbs()
        self._mark_dirty()
        self.render_page(scroll="top")
        self.statusBar().showMessage("Undone", 2500)

    # ---- page operations ---------------------------------------------------------------
    def rotate(self, delta):
        if not self.doc:
            return
        pages = self._selected_pages()
        self._push_undo()
        for p in pages:
            pg = self.doc[p]
            pg.set_rotation((pg.rotation + delta) % 360)
            self._refresh_thumb(p)
        self._mark_dirty()
        self.render_page()

    def delete_pages(self):
        if not self.doc:
            return
        pages = self._selected_pages()
        if len(pages) >= len(self.doc):
            QMessageBox.warning(self, "Delete pages", "A PDF must keep at least one page.")
            return
        self._push_undo()
        for p in sorted(pages, reverse=True):
            self.doc.delete_page(p)
        self.current = min(pages[0], len(self.doc) - 1)
        self._build_thumbs()
        self._mark_dirty()
        self.render_page(scroll="top")
        self.statusBar().showMessage(f"Deleted {len(pages)} page(s)  (Ctrl+Z to undo)", 4000)

    def _apply_order(self, order, keep_pages):
        """Reorder the document. order[i] = old index of the page now at position i."""
        self._push_undo()
        old_current = self.current
        self.doc.select(order)
        self.current = order.index(old_current)
        self._build_thumbs()
        self._sync = True
        self.thumbs.clearSelection()
        for old in keep_pages:
            self.thumbs.item(order.index(old)).setSelected(True)
        self._sync = False
        self._mark_dirty()
        self.render_page(scroll="top")

    def move_pages(self, direction):
        if not self.doc:
            return
        sel = set(self._selected_pages())
        n = len(self.doc)
        order = list(range(n))
        if direction < 0:
            for i in range(1, n):
                if order[i] in sel and order[i - 1] not in sel:
                    order[i - 1], order[i] = order[i], order[i - 1]
        else:
            for i in range(n - 2, -1, -1):
                if order[i] in sel and order[i + 1] not in sel:
                    order[i + 1], order[i] = order[i], order[i + 1]
        if order != list(range(n)):
            self._apply_order(order, sel)

    def _on_reordered(self):
        if not self.doc:
            return
        order = [self.thumbs.item(r).data(Qt.ItemDataRole.UserRole) for r in range(self.thumbs.count())]
        if order == list(range(len(self.doc))):
            return
        sel = {self.thumbs.item(r).data(Qt.ItemDataRole.UserRole)
               for r in range(self.thumbs.count()) if self.thumbs.item(r).isSelected()}
        QTimer.singleShot(0, lambda: self._apply_order(order, sel))

    def merge_pdfs(self, after_current):
        if not self.doc:
            return
        names, _ = QFileDialog.getOpenFileNames(self, "Select PDF(s) to add", self.last_dir, "PDF Files (*.pdf)")
        if not names:
            return
        self._push_undo()
        pos = self.current + 1 if after_current else len(self.doc)
        first = pos
        added = 0
        for name in names:
            d2, _ = self._authenticated_doc(name)
            if d2 is None:
                continue
            try:
                self.doc.insert_pdf(d2, start_at=pos)
                pos += len(d2)
                added += len(d2)
            except Exception as e:
                QMessageBox.warning(self, "Merge failed", f"{os.path.basename(name)}\n\n{e}")
            finally:
                d2.close()
        if not added:
            self.undo_stack.pop()
            return
        self.last_dir = os.path.dirname(names[0])
        self.current = first
        self._build_thumbs()
        self._mark_dirty()
        self.render_page(scroll="top")
        self.statusBar().showMessage(f"Added {added} page(s)  \u2014  remember to Save", 5000)

    def extract_pages(self):
        if not self.doc:
            return
        pages = self._selected_pages()
        stem = Path(self.path).stem if self.path else "document"
        default = os.path.join(self.last_dir, f"{stem}_p{pages[0] + 1}"
                               + (f"-{pages[-1] + 1}" if len(pages) > 1 else "") + ".pdf")
        name, _ = QFileDialog.getSaveFileName(self, "Save extracted pages", default, "PDF Files (*.pdf)")
        if not name:
            return
        name = name if name.lower().endswith(".pdf") else name + ".pdf"
        try:
            new = fitz.open()
            for a, b in ranges(pages):
                new.insert_pdf(self.doc, from_page=a, to_page=b)
            new.save(name, garbage=3, deflate=True)
            new.close()
        except Exception as e:
            QMessageBox.warning(self, "Extract failed", str(e))
            return
        self.last_dir = os.path.dirname(name)
        self.statusBar().showMessage(f"Saved {len(pages)} page(s) to {os.path.basename(name)}", 5000)

    def split_pages(self):
        if not self.doc:
            return
        folder = QFileDialog.getExistingDirectory(self, "Folder for single pages", self.last_dir)
        if not folder:
            return
        stem = Path(self.path).stem if self.path else "page"
        n = len(self.doc)
        width = len(str(n))
        targets = [os.path.join(folder, f"{stem}_{i + 1:0{width}d}.pdf") for i in range(n)]
        if any(os.path.exists(t) for t in targets):
            if QMessageBox.question(self, "Overwrite?", "Some files already exist in that folder. Overwrite them?") \
                    != QMessageBox.StandardButton.Yes:
                return
        dlg = QProgressDialog("Splitting...", "Cancel", 0, n, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(300)
        done = 0
        try:
            for i, t in enumerate(targets):
                dlg.setValue(i)
                if dlg.wasCanceled():
                    break
                new = fitz.open()
                new.insert_pdf(self.doc, from_page=i, to_page=i)
                new.save(t, garbage=3, deflate=True)
                new.close()
                done += 1
        except Exception as e:
            QMessageBox.warning(self, "Split failed", str(e))
        dlg.setValue(n)
        self.last_dir = folder
        self.statusBar().showMessage(f"Wrote {done} file(s) to {folder}", 6000)

    def export_png(self):
        if not self.doc:
            return
        stem = Path(self.path).stem if self.path else "page"
        default = os.path.join(self.last_dir, f"{stem}_p{self.current + 1}.png")
        name, _ = QFileDialog.getSaveFileName(self, "Export page as PNG", default, "PNG Image (*.png)")
        if not name:
            return
        name = name if name.lower().endswith(".png") else name + ".png"
        try:
            self.doc[self.current].get_pixmap(dpi=200, alpha=False).save(name)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self.statusBar().showMessage(f"Exported {os.path.basename(name)}", 4000)

    # ---- saving ---------------------------------------------------------------------------
    def save(self):
        if not self.doc:
            return False
        if not self.path:
            return self.save_as()
        return self._write(self.path)

    def save_as(self):
        if not self.doc:
            return False
        default = self.path or os.path.join(self.last_dir, "document.pdf")
        name, _ = QFileDialog.getSaveFileName(self, "Save PDF", default, "PDF Files (*.pdf)")
        if not name:
            return False
        return self._write(name if name.lower().endswith(".pdf") else name + ".pdf")

    def _write(self, path):
        """Atomic save: write to a temp file next to the target, then replace it."""
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(suffix=".pdf", prefix=".vvpdf_",
                                       dir=os.path.dirname(os.path.abspath(path)))
            os.close(fd)
            opts = dict(garbage=3, deflate=True)
            if self.password is not None:            # an authenticated doc would be saved decrypted
                opts.update(encryption=fitz.PDF_ENCRYPT_AES_256,
                            user_pw=self.password, owner_pw=self.password)
            self.doc.save(tmp, **opts)
            if os.path.exists(path):
                shutil.copymode(path, tmp)         # keep the original permissions
            os.replace(tmp, path)
            tmp = None
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return False
        finally:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        cur = self.current
        ok = self.open_path(path, password=self.password, keep_page=cur, keep_undo=True)
        if ok:
            self.statusBar().showMessage(f"Saved {os.path.basename(path)}", 4000)
        return ok

    # ---- search ---------------------------------------------------------------------------
    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _leave_search(self):
        self.search.clear()
        self.hits, self.hit_idx = [], -1
        self.render_page()
        self.scroll.setFocus()

    def _run_search(self):
        q = self.search.text().strip()
        self.hits, self.hit_idx = [], -1
        if not self.doc or not q:
            self.render_page()
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for pno in range(len(self.doc)):
                for r in self.doc[pno].search_for(q):
                    self.hits.append((pno, fitz.Rect(r)))
        finally:
            QApplication.restoreOverrideCursor()
        if not self.hits:
            self.statusBar().showMessage(f"No matches for \u201c{q}\u201d", 4000)
            self.render_page()
            return
        idx = next((i for i, (p, _) in enumerate(self.hits) if p >= self.current), 0)
        self._goto_hit(idx)

    def _step_hit(self, d):
        if not self.doc:
            return
        if not self.hits:
            if self.search.text().strip():
                self._run_search()
            return
        self._goto_hit((self.hit_idx + d) % len(self.hits))

    def _goto_hit(self, idx):
        self.hit_idx = idx
        pno, rect = self.hits[idx]
        self.current = pno
        self._sync = True
        self.thumbs.setCurrentRow(pno)
        self._sync = False
        rr = fitz.Rect(rect) * self.doc[pno].rotation_matrix
        k = self._scale_px / self.devicePixelRatioF()
        self.render_page(scroll=("hit", rr.x0 * k, rr.y0 * k))
        self.statusBar().showMessage(f"Match {idx + 1} of {len(self.hits)}  \u2014  Enter / F3 next, Shift+Enter previous", 4000)

    # ---- properties ------------------------------------------------------------------------
    def show_properties(self):
        if not self.doc:
            return
        md = self.doc.metadata or {}
        r = self.doc[self.current].rect
        rows = [
            ("File", self.path or "(unsaved)"),
            ("Size", fmt_size(os.path.getsize(self.path)) if self.path and os.path.exists(self.path) else "-"),
            ("Pages", str(len(self.doc))),
            ("Page size", f"{r.width / 72 * 25.4:.0f} \u00d7 {r.height / 72 * 25.4:.0f} mm"),
            ("Title", md.get("title") or "-"),
            ("Author", md.get("author") or "-"),
            ("Creator", md.get("creator") or "-"),
            ("Producer", md.get("producer") or "-"),
            ("Created", md.get("creationDate") or "-"),
            ("Encrypted", "yes" if (self.doc.is_encrypted or self.password is not None) else "no"),
        ]
        QMessageBox.information(self, "Document properties", "\n".join(f"{k}:  {v}" for k, v in rows))


# --------------------------------------------------------------------------
def apply_dark_palette(app):
    pal = QPalette()
    for role, color in {
        QPalette.ColorRole.Window: "#0b0b0e", QPalette.ColorRole.WindowText: "#e2e2e5",
        QPalette.ColorRole.Base: "#0b0b0e", QPalette.ColorRole.AlternateBase: "#15151a",
        QPalette.ColorRole.Text: "#e2e2e5", QPalette.ColorRole.Button: "#15151a",
        QPalette.ColorRole.ButtonText: "#e2e2e5", QPalette.ColorRole.ToolTipBase: "#15151a",
        QPalette.ColorRole.ToolTipText: "#e2e2e5", QPalette.ColorRole.Highlight: "#2a2a32",
        QPalette.ColorRole.HighlightedText: "#ffffff",
    }.items():
        pal.setColor(role, QColor(color))
    app.setPalette(pal)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VaeVictis PDF Tool")
    app.setStyle("Fusion")
    apply_dark_palette(app)
    app.setStyleSheet(STYLESHEET)
    win = VaeVictisPDF()
    win.show()
    for arg in sys.argv[1:]:
        if os.path.isfile(arg):
            win.open_path(arg)
            break
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
