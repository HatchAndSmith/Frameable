from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui import theme
from ui.widgets.led import LED


def _rule() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet(f"background: {theme.BORDER};")
    return w


class ScoringPanel(QWidget):
    def __init__(self, cloud_scorer=None, parent=None):
        super().__init__(parent)
        self._cloud = cloud_scorer

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_rule())
        header = QLabel("SCORING")
        header.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 9px; letter-spacing: 0.14em;"
        )
        header.setContentsMargins(0, 10, 0, 10)
        layout.addWidget(header)

        self._google_row = self._make_row("GOOGLE VISION", "G")
        self._replicate_row = self._make_row("REPLICATE", "R")
        self._offline_row = self._make_row("OFFLINE", "0")

        layout.addWidget(self._google_row["widget"])
        layout.addSpacing(4)
        layout.addWidget(self._replicate_row["widget"])
        layout.addSpacing(4)
        layout.addWidget(self._offline_row["widget"])

        self.refresh()

    def _make_row(self, name: str, code: str) -> dict:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        code_lbl = QLabel(f"[{code}]")
        code_lbl.setFixedWidth(22)
        code_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 10px;")

        name_lbl = QLabel(name)
        name_lbl.setFixedWidth(140)
        name_lbl.setStyleSheet(f"color: {theme.TEXT}; font-size: 10px;")

        led = LED()

        status_lbl = QLabel("")
        status_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 10px;")

        row.addWidget(code_lbl)
        row.addWidget(name_lbl)
        row.addWidget(led)
        row.addWidget(status_lbl)
        row.addStretch()

        return {"widget": w, "led": led, "status": status_lbl}

    def refresh(self):
        if self._cloud is None:
            self._set_row(self._google_row, False, theme.BORDER, "NO KEY")
            self._set_row(self._replicate_row, False, theme.BORDER, "NO KEY")
            self._set_row(self._offline_row, True, theme.GOOD, "ACTIVE")
            return

        # Google
        if self._cloud._google_key:
            remaining = self._cloud.tracker.google_remaining
            if remaining > 0:
                self._set_row(self._google_row, True, theme.GOOD,
                              f"{remaining} / 1000 REMAINING")
            else:
                self._set_row(self._google_row, False, theme.WARN, "LIMIT REACHED")
        else:
            self._set_row(self._google_row, False, theme.BORDER, "NO KEY")

        # Replicate
        if self._cloud._replicate_token:
            self._set_row(self._replicate_row, True, theme.GOOD, "CREDITS AVAILABLE")
        else:
            self._set_row(self._replicate_row, False, theme.BORDER, "NO KEY")

        # Offline always active
        self._set_row(self._offline_row, True, theme.GOOD, "ALWAYS ACTIVE")

    def _set_row(self, row: dict, active: bool, color: str, text: str):
        row["led"].set_state(active, color)
        row["status"].setText(text)
        row["status"].setStyleSheet(f"color: {color if active else theme.TEXT_DIM}; font-size: 10px;")

    def set_cloud_scorer(self, cloud_scorer):
        self._cloud = cloud_scorer
        self.refresh()
