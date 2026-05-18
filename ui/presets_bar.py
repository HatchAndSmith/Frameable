from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QVBoxLayout, QWidget)

from config import presets as preset_store
from ui import theme


def _rule() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet(f"background: {theme.BORDER};")
    return w


class _NameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SAVE PRESET")
        self.setModal(True)
        self.setMinimumWidth(340)
        self.setStyleSheet(f"QDialog {{ background: {theme.BG}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        lbl = QLabel("PRESET NAME")
        lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 9px; letter-spacing: 0.12em;"
        )
        layout.addWidget(lbl)

        self._edit = QLineEdit()
        self._edit.setStyleSheet(f"""
            QLineEdit {{
                background: {theme.SURFACE}; color: {theme.TEXT};
                border: 1px solid {theme.BORDER}; padding: 6px 10px; font-size: 11px;
            }}
        """)
        self._edit.setPlaceholderText("e.g. Wedding Mode")
        layout.addWidget(self._edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        cancel = QPushButton("CANCEL")
        cancel.setObjectName("cancel_btn")
        cancel.clicked.connect(self.reject)
        save = QPushButton("SAVE")
        save.clicked.connect(self._accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

        self._edit.returnPressed.connect(self._accept)
        self.result_name: str = ""

    def _accept(self):
        name = self._edit.text().strip()
        if name:
            self.result_name = name
            self.accept()


class PresetsBar(QWidget):
    preset_loaded = Signal(dict)  # emits settings dict

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(_rule())

        header = QLabel("PRESETS")
        header.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 9px; letter-spacing: 0.14em;"
        )
        header.setContentsMargins(0, 10, 0, 10)
        layout.addWidget(header)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        self._combo.setStyleSheet(f"""
            QComboBox {{
                background: {theme.SURFACE}; color: {theme.TEXT};
                border: 1px solid {theme.BORDER};
                padding: 4px 10px;
                font-family: "{theme.FONT_PRIMARY}", "{theme.FONT_FALLBACK}";
                font-size: 10px;
                min-width: 180px;
            }}
            QComboBox::drop-down {{
                border: none; width: 20px;
            }}
            QComboBox::down-arrow {{
                width: 6px; height: 6px;
                border-left: 1px solid {theme.TEXT_DIM};
                border-bottom: 1px solid {theme.TEXT_DIM};
                margin-right: 6px;
            }}
            QComboBox QAbstractItemView {{
                background: {theme.SURFACE}; color: {theme.TEXT};
                border: 1px solid {theme.BORDER};
                selection-background-color: {theme.ACCENT};
                selection-color: {theme.BG};
                font-size: 10px;
                outline: none;
            }}
        """)
        self._refresh_combo()

        load_btn = QPushButton("LOAD")
        load_btn.setFixedWidth(60)
        load_btn.clicked.connect(self._load)

        save_btn = QPushButton("SAVE")
        save_btn.setFixedWidth(60)
        save_btn.clicked.connect(self._save)

        self._del_btn = QPushButton("DEL")
        self._del_btn.setFixedWidth(50)
        self._del_btn.setObjectName("cancel_btn")
        self._del_btn.clicked.connect(self._delete)

        row.addWidget(self._combo)
        row.addWidget(load_btn)
        row.addWidget(save_btn)
        row.addWidget(self._del_btn)
        row.addStretch()
        layout.addLayout(row)

        self._current_settings: dict = {}  # populated via inject_settings()

        self._combo.currentTextChanged.connect(self._on_selection_changed)
        self._on_selection_changed(self._combo.currentText())

    def _refresh_combo(self):
        self._combo.blockSignals(True)
        current = self._combo.currentText()
        self._combo.clear()
        for name in preset_store.names():
            self._combo.addItem(name)
        idx = self._combo.findText(current)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        self._combo.blockSignals(False)
        self._on_selection_changed(self._combo.currentText())

    def _on_selection_changed(self, name: str):
        self._del_btn.setEnabled(bool(name) and not preset_store.is_built_in(name))

    def _load(self):
        name = self._combo.currentText()
        data = preset_store.get(name)
        if data:
            self.preset_loaded.emit(data)

    def _save(self):
        # current_settings must be injected before calling
        dialog = _NameDialog(self)
        if dialog.exec() and dialog.result_name:
            preset_store.save(dialog.result_name, self._current_settings)
            self._refresh_combo()
            idx = self._combo.findText(dialog.result_name)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

    def _delete(self):
        name = self._combo.currentText()
        if name and not preset_store.is_built_in(name):
            preset_store.delete(name)
            self._refresh_combo()

    def inject_settings(self, settings: dict):
        self._current_settings = dict(settings)
