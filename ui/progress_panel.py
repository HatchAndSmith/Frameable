import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QScrollArea,
                                QSizePolicy, QVBoxLayout, QWidget)

from ui import theme
from ui.widgets.meter import SegmentedMeter


def _rule() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet(f"background: {theme.BORDER};")
    return w


def _fmt_meta(duration: float, size_bytes: int) -> str:
    parts: list[str] = []
    if duration > 0:
        h = int(duration // 3600)
        m = int((duration % 3600) // 60)
        s = int(duration % 60)
        parts.append(f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}")
    if size_bytes > 0:
        if size_bytes >= 1_073_741_824:
            parts.append(f"{size_bytes / 1_073_741_824:.1f}GB")
        elif size_bytes >= 1_048_576:
            parts.append(f"{size_bytes / 1_048_576:.0f}MB")
        else:
            parts.append(f"{size_bytes / 1024:.0f}KB")
    return "  ·  ".join(parts)


class VideoProgressRow(QWidget):
    skip_requested = Signal(str)  # video name

    def __init__(self, name: str, duration: float = 0.0,
                 size_bytes: int = 0, parent=None):
        super().__init__(parent)
        self.name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(12)

        name_lbl = QLabel(name)
        name_lbl.setMinimumWidth(180)
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        name_lbl.setStyleSheet(f"color: {theme.TEXT}; font-size: 12px;")
        name_lbl.setToolTip(name)

        self._meta_lbl = QLabel(_fmt_meta(duration, size_bytes))
        self._meta_lbl.setFixedWidth(124)
        self._meta_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.06em;"
        )

        self._meter = SegmentedMeter(segments=18)
        self._meter.setFixedWidth(180)

        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setFixedWidth(40)
        self._pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._pct_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")

        self._frames_lbl = QLabel("")
        self._frames_lbl.setFixedWidth(78)
        self._frames_lbl.setStyleSheet(f"color: {theme.ACCENT}; font-size: 11px;")

        self._skip_btn = QPushButton("SKIP")
        self._skip_btn.setFixedSize(52, 22)
        self._skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {theme.TEXT_DIM};
                border: 1px solid {theme.BORDER};
                font-size: 9px;
                padding: 0;
                letter-spacing: 0.14em;
            }}
            QPushButton:hover {{
                color: {theme.WARN};
                border-color: {theme.WARN};
            }}
            QPushButton:disabled {{
                color: {theme.BORDER};
                border-color: {theme.BORDER};
            }}
        """)
        self._skip_btn.setToolTip("Skip this file")
        self._skip_btn.clicked.connect(self._on_skip)

        layout.addWidget(name_lbl)
        layout.addWidget(self._meta_lbl)
        layout.addWidget(self._meter)
        layout.addWidget(self._pct_lbl)
        layout.addWidget(self._frames_lbl)
        layout.addWidget(self._skip_btn)

    def _on_skip(self):
        self._skip_btn.setEnabled(False)
        self._skip_btn.setText("…")
        self.skip_requested.emit(self.name)

    def update_progress(self, progress: float, frames: int = 0):
        self._meter.set_progress(progress)
        self._pct_lbl.setText(f"{int(progress * 100)}%")
        if frames > 0:
            self._frames_lbl.setText(f"{frames} FR")

    def set_done(self, frames: int):
        self._meter.set_done()
        self._pct_lbl.setStyleSheet(f"color: {theme.GOOD}; font-size: 11px;")
        self._pct_lbl.setText("DONE")
        if frames > 0:
            self._frames_lbl.setStyleSheet(f"color: {theme.GOOD}; font-size: 11px;")
            self._frames_lbl.setText(f"{frames} FR")
        else:
            self._frames_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
            self._frames_lbl.setText("0 FR")
        self._skip_btn.hide()

    def set_skipped(self):
        self._pct_lbl.setStyleSheet(f"color: {theme.WARN}; font-size: 11px;")
        self._pct_lbl.setText("SKIP")
        self._frames_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        self._frames_lbl.setText("")
        self._skip_btn.hide()

    def set_error(self, msg: str):
        self._pct_lbl.setStyleSheet(f"color: {theme.ERROR}; font-size: 11px;")
        self._pct_lbl.setText("ERR")
        self._frames_lbl.setStyleSheet(f"color: {theme.ERROR}; font-size: 11px;")
        self._frames_lbl.setText(msg[:14])
        self._skip_btn.hide()


class ProgressPanel(QWidget):
    skip_requested = Signal(str)  # forwards row skip clicks

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, VideoProgressRow] = {}
        self._start_time: float = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_rule())
        header = QLabel("PROCESSING")
        header.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.14em;"
        )
        header.setContentsMargins(0, 10, 0, 10)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setMinimumHeight(180)
        scroll.setMaximumHeight(360)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)
        self._inner_layout.addStretch()
        scroll.setWidget(self._inner)
        layout.addWidget(scroll)

        layout.addSpacing(10)

        overall_row = QHBoxLayout()
        overall_row.setSpacing(14)

        overall_lbl = QLabel("TOTAL")
        overall_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.12em;"
        )
        overall_lbl.setFixedWidth(60)

        self._overall_meter = SegmentedMeter(segments=24)
        self._overall_meter.setMinimumWidth(160)

        self._overall_lbl = QLabel("0 / 0 VIDEOS")
        self._overall_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        self._total_frames_lbl = QLabel("0 FRAMES SAVED")
        self._total_frames_lbl.setStyleSheet(f"color: {theme.ACCENT}; font-size: 12px;")

        overall_row.addWidget(overall_lbl)
        overall_row.addWidget(self._overall_meter)
        overall_row.addWidget(self._overall_lbl)
        overall_row.addWidget(self._total_frames_lbl)
        overall_row.addStretch()
        layout.addLayout(overall_row)

        layout.addSpacing(6)

        eta_row = QHBoxLayout()
        eta_row.setContentsMargins(74, 0, 0, 0)
        self._eta_lbl = QLabel("")
        self._eta_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;")
        eta_row.addWidget(self._eta_lbl)
        eta_row.addStretch()
        layout.addLayout(eta_row)

        self._total = 0
        self._done = 0
        self._total_frames = 0

    def start_batch(self, items: list[tuple[str, float, int]]):
        """items: list of (name, duration_sec, size_bytes)."""
        for row in self._rows.values():
            self._inner_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        self._total = len(items)
        self._done = 0
        self._total_frames = 0
        self._start_time = time.monotonic()
        self._overall_meter.reset()
        self._overall_lbl.setText(f"0 / {self._total} VIDEOS")
        self._total_frames_lbl.setText("0 FRAMES SAVED")
        self._eta_lbl.setText("")

        for name, dur, size in items:
            row = VideoProgressRow(name, duration=dur, size_bytes=size)
            row.skip_requested.connect(self.skip_requested)
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
        self._refresh_overall()

    def video_skipped(self, name: str):
        row = self._rows.get(name)
        if row:
            row.set_skipped()
        self._done += 1
        self._refresh_overall()

    def video_error(self, name: str, msg: str):
        row = self._rows.get(name)
        if row:
            row.set_error(msg)
        self._done += 1
        self._refresh_overall()

    def _refresh_overall(self):
        frac = self._done / max(self._total, 1)
        self._overall_meter.set_progress(frac)
        self._overall_lbl.setText(f"{self._done} / {self._total} VIDEOS")
        self._total_frames_lbl.setText(f"{self._total_frames} FRAMES SAVED")

        elapsed = time.monotonic() - self._start_time
        if 0 < frac < 1.0:
            remaining = (elapsed / frac) - elapsed
            mins, secs = int(remaining // 60), int(remaining % 60)
            if mins > 0:
                self._eta_lbl.setText(f"EST. {mins}m {secs:02d}s REMAINING")
            else:
                self._eta_lbl.setText(f"EST. {secs}s REMAINING")
        elif frac >= 1.0:
            self._overall_meter.set_done()
            self._total_frames_lbl.setStyleSheet(f"color: {theme.GOOD}; font-size: 12px;")
            e_mins, e_secs = int(elapsed // 60), int(elapsed % 60)
            if e_mins > 0:
                self._eta_lbl.setText(f"COMPLETED IN {e_mins}m {e_secs:02d}s")
            else:
                self._eta_lbl.setText(f"COMPLETED IN {e_secs}s")
