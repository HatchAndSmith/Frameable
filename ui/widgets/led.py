from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ui import theme


class LED(QWidget):
    def __init__(self, color: str = theme.GOOD, parent=None):
        super().__init__(parent)
        self._color = color
        self._active = True
        self.setFixedSize(QSize(8, 8))

    def set_state(self, active: bool, color: str | None = None):
        self._active = active
        if color:
            self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        c = QColor(self._color if self._active else theme.BORDER)
        p.fillRect(self.rect(), c)
        p.end()
