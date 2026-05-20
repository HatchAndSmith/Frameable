from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton,
                                QScrollArea, QSizePolicy, QVBoxLayout,
                                QWidget)

from ui import theme


def _format_duration(secs: float) -> str:
    total = int(secs)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _format_size(path: Path) -> str:
    try:
        b = path.stat().st_size
        if b >= 1_073_741_824:
            return f"{b/1_073_741_824:.1f} GB"
        if b >= 1_048_576:
            return f"{b/1_048_576:.0f} MB"
        return f"{b/1024:.0f} KB"
    except Exception:
        return "?"


class FileRow(QWidget):
    remove_requested = Signal(Path)

    STATUS_COLORS = {
        "ready": theme.TEXT_DIM,
        "processing": theme.ACCENT,
        "done": theme.GOOD,
        "error": theme.ERROR,
        "queue": theme.TEXT_DIM,
    }

    def __init__(self, path: Path, duration: float | None = None, codec: str = "", parent=None):
        super().__init__(parent)
        self.path = path
        self._status = "ready"

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(16)

        name = QLabel(path.name)
        name.setStyleSheet(f"color: {theme.TEXT}; font-size: 11px;")
        name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        name.setToolTip(str(path))

        dur_str = _format_duration(duration) if duration is not None else "--:--"
        dur_lbl = QLabel(dur_str)
        dur_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 10px; min-width: 44px;")
        dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        codec_lbl = QLabel(codec.upper() if codec else "")
        codec_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 10px; min-width: 54px;")

        self._status_lbl = QLabel("READY")
        self._status_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.08em; min-width: 60px;"
        )

        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {theme.TEXT_DIM};
                font-size: 10px;
                padding: 0;
            }}
            QPushButton:hover {{ color: {theme.TEXT}; }}
        """)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.path))

        layout.addWidget(name)
        layout.addWidget(dur_lbl)
        layout.addWidget(codec_lbl)
        layout.addWidget(self._status_lbl)
        layout.addWidget(remove_btn)
        self.setStyleSheet(f"background: {theme.BG}; border-bottom: 1px solid {theme.BORDER};")

    def set_status(self, status: str, label: str | None = None):
        self._status = status
        text = (label or status).upper()
        color = self.STATUS_COLORS.get(status, theme.TEXT_DIM)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-size: 10px; letter-spacing: 0.08em; min-width: 60px;"
        )
        self._status_lbl.setText(text)


class FileListWidget(QWidget):
    list_changed = Signal(int)  # emits new count

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[Path, FileRow] = {}
        self._durations: dict[Path, float] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(26)
        header.setStyleSheet(f"background: {theme.SURFACE2};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.setSpacing(16)
        for txt, stretch in [("FILE", True), ("DURATION", False),
                              ("CODEC", False), ("STATUS", False), ("", False)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(
                f"color: {theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.12em;"
            )
            if stretch:
                lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            hl.addWidget(lbl)
        outer.addWidget(header)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(self._scroll.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMinimumHeight(120)
        self._scroll.setMaximumHeight(280)

        self._inner = QWidget()
        self._inner.setStyleSheet(f"background: {theme.BG};")
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)
        self._inner_layout.addStretch()

        self._empty_lbl = QLabel("NO FILES ADDED")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.10em; padding: 24px;"
        )
        self._inner_layout.insertWidget(0, self._empty_lbl)

        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll)

        # Footer
        self._footer = QWidget()
        self._footer.setFixedHeight(28)
        self._footer.setStyleSheet(f"background: {theme.SURFACE2};")
        fl = QHBoxLayout(self._footer)
        fl.setContentsMargins(12, 0, 8, 0)
        self._count_lbl = QLabel("0 FILES")
        self._count_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 11px; letter-spacing: 0.10em;"
        )
        clear_btn = QPushButton("CLEAR ALL")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {theme.TEXT_DIM}; font-size: 11px;
                letter-spacing: 0.10em; padding: 0;
            }}
            QPushButton:hover {{ color: {theme.TEXT}; }}
        """)
        clear_btn.clicked.connect(self.clear_all)
        fl.addWidget(self._count_lbl)
        fl.addStretch()
        fl.addWidget(clear_btn)
        outer.addWidget(self._footer)

    def add_files(self, paths: list[Path], durations: dict[Path, float] | None = None,
                  codecs: dict[Path, str] | None = None):
        for p in paths:
            if p in self._rows:
                continue
            dur = (durations or {}).get(p)
            if dur is not None:
                self._durations[p] = dur
            codec = (codecs or {}).get(p, "")
            row = FileRow(p, duration=dur, codec=codec)
            row.remove_requested.connect(self._remove)
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, row)
            self._rows[p] = row
        self._refresh()

    def _remove(self, path: Path):
        row = self._rows.pop(path, None)
        if row:
            self._inner_layout.removeWidget(row)
            row.deleteLater()
        self._durations.pop(path, None)
        self._refresh()

    def clear_all(self):
        for row in list(self._rows.values()):
            self._inner_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
        self._durations.clear()
        self._refresh()

    def _refresh(self):
        n = len(self._rows)
        self._empty_lbl.setVisible(n == 0)
        total_dur = sum(self._durations.values())
        if total_dur > 0:
            h = int(total_dur // 3600)
            m = int((total_dur % 3600) // 60)
            s = int(total_dur % 60)
            dur_str = f"  —  {h}h {m:02d}m" if h > 0 else f"  —  {m}m {s:02d}s"
            self._count_lbl.setText(f"{n} FILE{'S' if n != 1 else ''}{dur_str}")
        else:
            self._count_lbl.setText(f"{n} FILE{'S' if n != 1 else ''}")
        self.list_changed.emit(n)

    def paths(self) -> list[Path]:
        return list(self._rows.keys())

    def duration(self, path: Path) -> float:
        return self._durations.get(path, 0.0)

    def set_status(self, path: Path, status: str, label: str | None = None):
        row = self._rows.get(path)
        if row:
            row.set_status(status, label)

    def lock(self, locked: bool):
        for row in self._rows.values():
            row.setEnabled(not locked)
