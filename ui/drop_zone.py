from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from core.extractor import SUPPORTED_EXTENSIONS
from ui import theme


class DropZone(QWidget):
    files_dropped = Signal(list)  # list[Path]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hover = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._top = QLabel("DROP VIDEO FILES HERE")
        self._top.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._top.setStyleSheet(f"""
            color: {theme.TEXT};
            font-size: 13px;
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

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        border_color = QColor(theme.TEXT_DIM if self._hover else theme.BORDER)
        pen = QPen(border_color, 1, Qt.PenStyle.DotLine)
        p.setPen(pen)
        p.setBrush(QColor(theme.SURFACE if self._hover else theme.BG))
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)
        p.end()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in event.mimeData().urls()]
            if any(p.suffix.lower() in SUPPORTED_EXTENSIONS or p.is_dir() for p in paths):
                event.acceptProposedAction()
                self._hover = True
                self.update()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._hover = False
        self.update()

    def dropEvent(self, event: QDropEvent):
        self._hover = False
        self.update()
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
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()
