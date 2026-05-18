from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ui import theme


class SegmentedMeter(QWidget):
    def __init__(self, segments: int = 24, parent=None):
        super().__init__(parent)
        self._segments = segments
        self._progress = 0.0
        self._done = False
        self.setFixedHeight(8)
        self.setMinimumWidth(120)

    def set_progress(self, value: float):
        self._progress = max(0.0, min(1.0, value))
        self._done = False
        self.update()

    def set_done(self):
        self._progress = 1.0
        self._done = True
        self.update()

    def reset(self):
        self._progress = 0.0
        self._done = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        gap = 2
        seg_w = max(2, (w - gap * (self._segments - 1)) / self._segments)
        filled_f = self._progress * self._segments

        active_color = QColor(theme.GOOD if self._done else theme.ACCENT)
        inactive_color = QColor(theme.SURFACE)

        for i in range(self._segments):
            x = int(i * (seg_w + gap))
            frac = min(1.0, max(0.0, filled_f - i))
            if frac >= 1.0:
                color = active_color
            elif frac > 0:
                color = QColor(active_color)
                color.setAlpha(int(frac * 255))
            else:
                color = inactive_color
            p.fillRect(x, 0, int(seg_w), h, color)
        p.end()
