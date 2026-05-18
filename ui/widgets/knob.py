import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ui import theme


class Knob(QWidget):
    value_changed = Signal(float)

    _START_ANGLE = 225   # degrees, clockwise from 3 o'clock in screen coords
    _SWEEP = 270         # total sweep in degrees

    def __init__(self, min_val: float = 0, max_val: float = 100,
                 value: float = 50, label: str = "", unit: str = "",
                 integer: bool = False, parent=None):
        super().__init__(parent)
        self._min = min_val
        self._max = max_val
        self._value = float(value)
        self._label = label
        self._unit = unit
        self._integer = integer
        self._drag_y = 0
        self._drag_val = 0.0
        self.setFixedSize(72, 80)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip(f"Drag up/down to adjust {label.lower()}")

    @property
    def value(self) -> float:
        return round(self._value) if self._integer else self._value

    def set_value(self, v: float, emit: bool = True):
        clamped = max(self._min, min(self._max, v))
        if clamped != self._value:
            self._value = clamped
            self.update()
            if emit:
                self.value_changed.emit(self.value)

    def _norm(self) -> float:
        span = self._max - self._min
        return (self._value - self._min) / span if span else 0.0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy, r = 36, 33, 22

        # Track ring
        p.setPen(QPen(QColor(theme.BORDER), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Value arc
        if self._norm() > 0:
            p.setPen(QPen(QColor(theme.ACCENT), 2))
            # Qt arc: start in 1/16th degrees, anti-clockwise positive
            # We want clockwise from _START_ANGLE
            qt_start = (90 - self._START_ANGLE) * 16  # convert to Qt's system
            qt_span = int(-self._SWEEP * self._norm() * 16)
            p.drawArc(cx - r + 3, cy - r + 3, (r - 3) * 2, (r - 3) * 2,
                      qt_start, qt_span)

        # Indicator dot
        angle_deg = self._START_ANGLE - self._norm() * self._SWEEP
        angle_rad = math.radians(angle_deg)
        ix = cx + (r - 6) * math.cos(angle_rad)
        iy = cy - (r - 6) * math.sin(angle_rad)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.TEXT))
        p.drawEllipse(int(ix) - 2, int(iy) - 2, 4, 4)

        # Value text
        val_str = f"{int(self.value)}" if self._integer else f"{self.value:.1f}"
        if self._unit:
            val_str += self._unit
        p.setPen(QColor(theme.TEXT))
        f = QFont(theme.FONT_PRIMARY)
        f.setPointSize(9)
        p.setFont(f)
        p.drawText(0, 52, 72, 14, Qt.AlignmentFlag.AlignCenter, val_str)

        # Label
        p.setPen(QColor(theme.TEXT_DIM))
        f2 = QFont(theme.FONT_PRIMARY)
        f2.setPointSize(7)
        p.setFont(f2)
        p.drawText(0, 65, 72, 14, Qt.AlignmentFlag.AlignCenter,
                   self._label.upper())

        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_y = event.globalPosition().y()
            self._drag_val = self._value

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            dy = self._drag_y - event.globalPosition().y()
            span = self._max - self._min
            delta = dy / 120.0 * span
            self.set_value(self._drag_val + delta)

    def mouseReleaseEvent(self, event):
        pass

    def wheelEvent(self, event):
        step = 1 if self._integer else (self._max - self._min) / 100
        delta = event.angleDelta().y() / 120.0 * step
        self.set_value(self._value + delta)
