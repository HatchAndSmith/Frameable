from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                                QPushButton, QVBoxLayout, QWidget)

from config import settings as cfg_store
from ui import theme


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {theme.TEXT_DIM}; font-size: 9px; letter-spacing: 0.12em;"
    )
    return lbl


def _rule() -> QWidget:
    w = QWidget()
    w.setFixedHeight(1)
    w.setStyleSheet(f"background: {theme.BORDER};")
    return w


class SettingsPanel(QDialog):
    keys_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SETTINGS")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{
                background: {theme.BG};
                color: {theme.TEXT};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(0)

        title = QLabel("SETTINGS")
        title.setStyleSheet(
            f"color: {theme.TEXT}; font-size: 13px; letter-spacing: 0.18em;"
        )
        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(_rule())

        # Google Vision
        layout.addSpacing(16)
        layout.addWidget(_label("GOOGLE VISION API KEY"))
        layout.addSpacing(6)
        self._google_edit = self._key_field()
        self._google_edit.setText(cfg_store.get_api_key("google_vision") or "")
        layout.addWidget(self._google_edit)

        layout.addSpacing(6)
        g_hint = QLabel(
            "console.cloud.google.com — Vision API — Credentials — Create API key"
        )
        g_hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 9px;")
        layout.addWidget(g_hint)

        layout.addSpacing(20)
        layout.addWidget(_rule())

        # Replicate
        layout.addSpacing(16)
        layout.addWidget(_label("REPLICATE API TOKEN"))
        layout.addSpacing(6)
        self._replicate_edit = self._key_field()
        self._replicate_edit.setText(cfg_store.get_api_key("replicate_token") or "")
        layout.addWidget(self._replicate_edit)

        layout.addSpacing(6)
        r_hint = QLabel("replicate.com — Account — API tokens — Create token")
        r_hint.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 9px;")
        layout.addWidget(r_hint)

        layout.addSpacing(20)
        layout.addWidget(_rule())

        # Usage reset
        layout.addSpacing(16)
        layout.addWidget(_label("API USAGE"))
        layout.addSpacing(8)
        reset_row = QHBoxLayout()
        reset_row.setSpacing(12)
        self._usage_lbl = QLabel("")
        self._usage_lbl.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 10px;")
        reset_btn = QPushButton("RESET GOOGLE COUNTER")
        reset_btn.setFixedHeight(28)
        reset_btn.clicked.connect(self._reset_google)
        reset_row.addWidget(self._usage_lbl)
        reset_row.addStretch()
        reset_row.addWidget(reset_btn)
        layout.addLayout(reset_row)

        layout.addSpacing(24)
        layout.addWidget(_rule())
        layout.addSpacing(16)

        # Save / cancel
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setObjectName("cancel_btn")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("SAVE")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self._refresh_usage()

    def _key_field(self) -> QLineEdit:
        e = QLineEdit()
        e.setEchoMode(QLineEdit.EchoMode.Password)
        e.setPlaceholderText("paste key here")
        e.setStyleSheet(f"""
            QLineEdit {{
                background: {theme.SURFACE};
                color: {theme.TEXT};
                border: 1px solid {theme.BORDER};
                padding: 6px 10px;
                font-size: 11px;
            }}
        """)
        return e

    def _refresh_usage(self):
        from core.cloud_scorer import UsageTracker
        tracker = UsageTracker(cfg_store.CONFIG_DIR)
        self._usage_lbl.setText(
            f"GOOGLE VISION  {tracker.google_used} / 1000  THIS MONTH"
        )

    def _reset_google(self):
        from core.cloud_scorer import UsageTracker
        UsageTracker(CONFIG_DIR).reset_google()
        self._refresh_usage()

    def _save(self):
        google_key = self._google_edit.text().strip()
        replicate_token = self._replicate_edit.text().strip()

        if google_key:
            cfg_store.set_api_key("google_vision", google_key)
        else:
            cfg_store.delete_api_key("google_vision")

        if replicate_token:
            cfg_store.set_api_key("replicate_token", replicate_token)
        else:
            cfg_store.delete_api_key("replicate_token")

        self.keys_updated.emit()
        self.accept()
