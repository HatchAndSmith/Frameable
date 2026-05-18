from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QScrollArea,
                                QSizePolicy, QVBoxLayout, QWidget)

from ui import theme
from ui.widgets.meter import SegmentedMeter


def _rule() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet(f"background: {theme.BORDER};")
    return w


class VideoProgressRow(QWidget):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(14)

        name_lbl = QLabel(name)
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        name_lbl.setStyleSheet(f"color: {theme.TEXT}; font-size: 10px;")
        name_lbl.setToolTip(name)

        self._meter = SegmentedMeter(segments=20)
        self._meter.setMinimumWidth(140)
        self._meter.setFixedWidth(200)

        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setFixedWidth(34)
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._pct_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 10px;")

        self._frames_lbl = QLabel("")
        self._frames_lbl.setFixedWidth(80)
        self._frames_lbl.setStyleSheet(f"color: {theme.ACCENT}; font-size: 10px;")

        layout.addWidget(name_lbl)
        layout.addWidget(self._meter)
        layout.addWidget(self._pct_lbl)
        layout.addWidget(self._frames_lbl)

    def update_progress(self, progress: float, frames: int = 0):
        self._meter.set_progress(progress)
        self._pct_lbl.setText(f"{int(progress * 100)}%")
        if frames > 0:
            self._frames_lbl.setText(f"{frames} FRAMES")

    def set_done(self, frames: int):
        self._meter.set_done()
        self._pct_lbl.setStyleSheet(f"color: {theme.GOOD}; font-size: 10px;")
        self._pct_lbl.setText("DONE")
        self._frames_lbl.setText(f"{frames} FRAMES")

    def set_error(self, msg: str):
        self._pct_lbl.setStyleSheet(f"color: {theme.ERROR}; font-size: 10px;")
        self._pct_lbl.setText("ERR")
        self._frames_lbl.setText(msg[:18])


class ProgressPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, VideoProgressRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_rule())
        header = QLabel("PROCESSING")
        header.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 9px; letter-spacing: 0.14em;"
        )
        header.setContentsMargins(0, 10, 0, 10)
        layout.addWidget(header)

        # Scroll area for per-video rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setMaximumHeight(160)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)
        self._inner_layout.addStretch()
        scroll.setWidget(self._inner)
        layout.addWidget(scroll)

        layout.addSpacing(8)

        # Overall row
        overall_row = QHBoxLayout()
        overall_row.setSpacing(14)

        overall_lbl = QLabel("TOTAL")
        overall_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 9px; letter-spacing: 0.12em;"
        )
        overall_lbl.setFixedWidth(60)

        self._overall_meter = SegmentedMeter(segments=24)
        self._overall_meter.setMinimumWidth(140)

        self._overall_lbl = QLabel("0 / 0 VIDEOS")
        self._overall_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 10px;")
        self._total_frames_lbl = QLabel("0 FRAMES TOTAL")
        self._total_frames_lbl.setStyleSheet(f"color: {theme.ACCENT}; font-size: 10px;")

        overall_row.addWidget(overall_lbl)
        overall_row.addWidget(self._overall_meter)
        overall_row.addWidget(self._overall_lbl)
        overall_row.addWidget(self._total_frames_lbl)
        overall_row.addStretch()
        layout.addLayout(overall_row)

        self._total = 0
        self._done = 0
        self._total_frames = 0

    def start_batch(self, names: list[str]):
        # Clear old rows
        for row in self._rows.values():
            self._inner_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        self._total = len(names)
        self._done = 0
        self._total_frames = 0
        self._overall_meter.reset()
        self._overall_lbl.setText(f"0 / {self._total} VIDEOS")
        self._total_frames_lbl.setText("0 FRAMES TOTAL")

        for name in names:
            row = VideoProgressRow(name)
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, row)
            self._rows[name] = row

    def update_video(self, name: str, progress: float, frames: int = 0):
        row = self._rows.get(name)
        if row:
            row.update_progress(progress, frames)

    def video_done(self, name: str, frames: int):
        row = self._rows.get(name)
        if row:
            row.set_done(frames)
        self._done += 1
        self._total_frames += frames
        self._overall_meter.set_progress(self._done / max(self._total, 1))
        self._overall_lbl.setText(f"{self._done} / {self._total} VIDEOS")
        self._total_frames_lbl.setText(f"{self._total_frames} FRAMES TOTAL")
        if self._done >= self._total:
            self._overall_meter.set_done()
            self._total_frames_lbl.setStyleSheet(f"color: {theme.GOOD}; font-size: 10px;")

    def video_error(self, name: str, msg: str):
        row = self._rows.get(name)
        if row:
            row.set_error(msg)
        self._done += 1
        self._overall_meter.set_progress(self._done / max(self._total, 1))
        self._overall_lbl.setText(f"{self._done} / {self._total} VIDEOS")
