from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ui import theme


class SegmentedMeter(QWidget):
    def __init__(self, segments: int = 24, parent=None):
        super().__init__(parent)
        self._segments = segments
        self._disp = 0.0   # animated display value
        self._done = False
        self.setFixedHeight(8)
        self.setMinimumWidth(120)

        self._anim = QPropertyAnimation(self, b"fill", self)
        self._anim.setDuration(350)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ── animated property ──────────────────────────────────────────────────

    def _get_fill(self) -> float:
        return self._disp

    def _set_fill(self, v: float):
        self._disp = v
        self.update()

    fill = Property(float, _get_fill, _set_fill)

    def _animate_to(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(self._disp)
        self._anim.setEndValue(target)
        self._anim.start()

    # ── public API ─────────────────────────────────────────────────────────

    def set_progress(self, value: float):
        self._done = False
        self._animate_to(max(0.0, min(1.0, value)))

    def set_done(self):
        self._done = True
        self._animate_to(1.0)

    def reset(self):
        self._anim.stop()
        self._done = False
        self._disp = 0.0
        self.update()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        gap = 2
        seg_w = max(2, (w - gap * (self._segments - 1)) / self._segments)
        filled_f = self._disp * self._segments

        active_color   = QColor(theme.GOOD if self._done else theme.ACCENT)
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
