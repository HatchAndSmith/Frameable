from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QLabel,
                                QPushButton, QRadioButton, QSpinBox,
                                QVBoxLayout, QWidget)

from ui import theme
from ui.widgets.knob import Knob


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {theme.TEXT_DIM}; font-size: 11px; letter-spacing: 0.14em;"
    )
    return lbl


def _rule() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet(f"background: {theme.BORDER};")
    return w


class OutputControls(QWidget):
    settings_changed = Signal()

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_rule())
        header = _section_label("OUTPUT")
        header.setContentsMargins(0, 10, 0, 10)
        layout.addWidget(header)

        # Mode row
        mode_row = QHBoxLayout()
        mode_row.setSpacing(24)
        mode_row.setContentsMargins(0, 0, 0, 0)

        self._auto_radio = QRadioButton("AUTO")
        self._manual_radio = QRadioButton("EXACT")
        self._auto_radio.setChecked(cfg.get("output_mode", "auto") == "auto")
        self._manual_radio.setChecked(cfg.get("output_mode", "auto") == "exact")
        self._auto_radio.toggled.connect(self._on_mode_change)

        self._spin = QSpinBox()
        self._spin.setRange(1, 9999)
        self._spin.setValue(cfg.get("exact_count", 50))
        self._spin.setEnabled(self._manual_radio.isChecked())
        self._spin.valueChanged.connect(self.settings_changed)

        mode_row.addWidget(self._auto_radio)
        mode_row.addWidget(self._manual_radio)
        mode_row.addWidget(self._spin)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        layout.addSpacing(14)

        # Knobs row
        knobs_row = QHBoxLayout()
        knobs_row.setSpacing(20)
        knobs_row.setContentsMargins(0, 0, 0, 0)

        self._blur_knob = Knob(0, 25, cfg.get("blur_mix_pct", 5),
                               label="BLUR MIX", unit="%", integer=True)
        self._blur_knob.value_changed.connect(self.settings_changed)

        self._rate_knob = Knob(4, 30, cfg.get("auto_frames_per_sec", 8),
                               label="SECS / STILL", integer=True)
        self._rate_knob.value_changed.connect(self.settings_changed)

        knobs_row.addWidget(self._blur_knob)
        knobs_row.addWidget(self._rate_knob)
        knobs_row.addStretch()
        layout.addLayout(knobs_row)

    def _on_mode_change(self):
        self._spin.setEnabled(self._manual_radio.isChecked())
        self.settings_changed.emit()

    def output_mode(self) -> str:
        return "auto" if self._auto_radio.isChecked() else "exact"

    def exact_count(self) -> int:
        return self._spin.value()

    def blur_pct(self) -> int:
        return int(self._blur_knob.value)

    def secs_per_frame(self) -> int:
        return int(self._rate_knob.value)

    # ── Setters for preset loading ─────────────────────────────────────────
    def apply_preset(self, data: dict):
        mode = data.get("output_mode", "auto")
        self._auto_radio.setChecked(mode == "auto")
        self._manual_radio.setChecked(mode == "exact")
        self._spin.setEnabled(mode == "exact")
        if "exact_count" in data:
            self._spin.setValue(int(data["exact_count"]))
        if "blur_mix_pct" in data:
            self._blur_knob.set_value(float(data["blur_mix_pct"]), emit=False)
        if "auto_frames_per_sec" in data:
            self._rate_knob.set_value(float(data["auto_frames_per_sec"]), emit=False)
        self._blur_knob.update()
        self._rate_knob.update()
        self.settings_changed.emit()


class DestinationControls(QWidget):
    settings_changed = Signal()

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._path = Path(cfg.get("last_output_dir", str(Path.home())))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_rule())
        header = _section_label("DESTINATION")
        header.setContentsMargins(0, 10, 0, 10)
        layout.addWidget(header)

        path_row = QHBoxLayout()
        path_row.setSpacing(10)
        self._path_lbl = QLabel(self._truncate(self._path))
        self._path_lbl.setStyleSheet(f"color: {theme.TEXT}; font-size: 12px;")
        self._path_lbl.setToolTip(str(self._path))

        browse_btn = QPushButton("BROWSE")
        browse_btn.setFixedWidth(80)
        browse_btn.setStyleSheet("QPushButton { padding: 5px 8px; font-size: 11px; }")
        browse_btn.clicked.connect(self._browse)

        path_row.addWidget(self._path_lbl)
        path_row.addStretch()
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        layout.addSpacing(8)

        self._sub_check = QCheckBox("SUBFOLDER PER VIDEO")
        self._sub_check.setChecked(cfg.get("subfolder_per_video", True))
        self._sub_check.toggled.connect(self.settings_changed)
        layout.addWidget(self._sub_check)

        layout.addSpacing(6)

        self._xmp_check = QCheckBox("WRITE XMP SIDECAR  (KEYWORDS)")
        self._xmp_check.setChecked(cfg.get("write_xmp", False))
        self._xmp_check.toggled.connect(self._on_xmp_toggle)
        layout.addWidget(self._xmp_check)

        self._angle_check = QCheckBox("  INCLUDE STRAIGHTEN ANGLE  (CENTER VERTICAL)")
        self._angle_check.setChecked(cfg.get("write_angle", False))
        self._angle_check.setEnabled(self._xmp_check.isChecked())
        self._angle_check.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 11px; letter-spacing: 0.08em;"
        )
        self._angle_check.toggled.connect(self.settings_changed)
        layout.addWidget(self._angle_check)

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Output Folder", str(self._path))
        if chosen:
            self._path = Path(chosen)
            self._path_lbl.setText(self._truncate(self._path))
            self._path_lbl.setToolTip(str(self._path))
            self.settings_changed.emit()

    def _on_xmp_toggle(self, checked: bool):
        self._angle_check.setEnabled(checked)
        if not checked:
            self._angle_check.setChecked(False)
        self.settings_changed.emit()

    def _truncate(self, p: Path) -> str:
        s = str(p)
        return s if len(s) < 60 else "..." + s[-57:]

    def output_dir(self) -> Path:
        return self._path

    def subfolder_per_video(self) -> bool:
        return self._sub_check.isChecked()

    def write_xmp(self) -> bool:
        return self._xmp_check.isChecked()

    def write_angle(self) -> bool:
        return self._angle_check.isChecked()

    def apply_preset(self, data: dict):
        if "subfolder_per_video" in data:
            self._sub_check.setChecked(bool(data["subfolder_per_video"]))
        if "write_xmp" in data:
            self._xmp_check.setChecked(bool(data["write_xmp"]))
        if "write_angle" in data:
            self._angle_check.setChecked(bool(data["write_angle"]))
        self.settings_changed.emit()
