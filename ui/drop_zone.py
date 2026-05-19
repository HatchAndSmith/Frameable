from pathlib import Path

from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation, Qt,
                             Signal)
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from core.extractor import SUPPORTED_EXTENSIONS
from ui import theme

_BG    = QColor(theme.BG)
_SURF  = QColor(theme.SURFACE)
_BORD  = QColor(theme.BORDER)
_DIM   = QColor(theme.TEXT_DIM)
_ACCNT = QColor(theme.ACCENT)


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        int(a.red()   + (b.red()   - a.red())   * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue()  + (b.blue()  - a.blue())  * t),
    )


class DropZone(QWidget):
    files_dropped = Signal(list)  # list[Path]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._alpha = 0.0   # 0 = cold, 1 = hot
        self._drag  = False

        self._anim = QPropertyAnimation(self, b"alpha", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._top = QLabel("DROP VIDEO FILES HERE")
        self._top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._top.setStyleSheet(f"""
            color: {theme.TEXT};
            font-size: 12px;
            letter-spacing: 0.18em;
            background: transparent;
        """)

        self._sub = QLabel("OR CLICK TO BROWSE  —  MP4  MOV  MKV  HEVC  PRORES  BRAW")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub.setStyleSheet(f"""
            color: {theme.TEXT_DIM};
            font-size: 9px;
            letter-spacing: 0.12em;
            background: transparent;
        """)

        layout.addWidget(self._top)
        layout.addWidget(self._sub)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── animated property ──────────────────────────────────────────────────

    def _get_alpha(self) -> float:
        return self._alpha

    def _set_alpha(self, v: float):
        self._alpha = v
        self.update()

    alpha = Property(float, _get_alpha, _set_alpha)

    def _animate(self, to: float):
        self._anim.stop()
        self._anim.setStartValue(self._alpha)
        self._anim.setEndValue(to)
        self._anim.start()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        t = self._alpha
        border_color = _lerp_color(_BORD, _ACCNT if self._drag else _DIM, t)
        fill = QColor(_SURF)
        fill.setAlpha(int(t * 40))

        pen = QPen(border_color, 1, Qt.PenStyle.DotLine)
        p.setPen(pen)
        p.setBrush(fill)
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)
        p.end()

    # ── drag events ────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in event.mimeData().urls()]
            if any(p.suffix.lower() in SUPPORTED_EXTENSIONS or p.is_dir()
                   for p in paths):
                event.acceptProposedAction()
                self._drag = True
                self._animate(1.0)
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._drag = False
        self._animate(0.0)

    def dropEvent(self, event: QDropEvent):
        self._drag = False
        self._animate(0.0)
        paths = []
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                paths.extend(
                    f for f in p.rglob("*")
                    if f.suffix.lower() in SUPPORTED_EXTENSIONS
                )
            elif p.suffix.lower() in SUPPORTED_EXTENSIONS:
                paths.append(p)
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

    # ── mouse events ───────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_dialog()

    def _open_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Video Files", "",
            "Video Files (*.mp4 *.mov *.m4v *.mkv *.avi *.mts *.m2ts "
            "*.wmv *.webm *.flv *.mxf *.braw *.r3d);;All Files (*)"
        )
        if paths:
            self.files_dropped.emit([Path(p) for p in paths])

    def enterEvent(self, event):
        self._animate(1.0)

    def leaveEvent(self, event):
        if not self._drag:
            self._animate(0.0)
