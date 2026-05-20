import logging

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QTextCursor, QGuiApplication
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit,
                                QPushButton, QVBoxLayout, QWidget)

from ui import theme

_LEVEL_COLORS = {
    logging.DEBUG:    theme.TEXT_DIM,
    logging.INFO:     theme.TEXT,
    logging.WARNING:  theme.WARN if hasattr(theme, "WARN") else "#E8A020",
    logging.ERROR:    theme.ERROR,
    logging.CRITICAL: theme.ERROR,
}


class _SignalHandler(QObject, logging.Handler):
    """Logging handler that emits a Qt signal for each record."""
    record_emitted = Signal(int, str)   # level, formatted text

    def __init__(self):
        QObject.__init__(self)
        logging.Handler.__init__(self)
        self.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                              datefmt="%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.record_emitted.emit(record.levelno, msg)
        except Exception:
            pass


# Module-level handler instance installed once
_handler: _SignalHandler | None = None


def install_handler() -> "_SignalHandler":
    global _handler
    if _handler is None:
        _handler = _SignalHandler()
        _handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(_handler)
    return _handler


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setFixedHeight(28)
        header.setStyleSheet(f"background: {theme.SURFACE2};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.setSpacing(8)

        title = QLabel("LOGS")
        title.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.14em;"
        )
        hl.addWidget(title)
        hl.addStretch()

        self._level_lbl = QLabel("")
        self._level_lbl.setStyleSheet(
            f"color: {theme.TEXT_DIM}; font-size: 10px; letter-spacing: 0.06em;"
        )
        hl.addWidget(self._level_lbl)

        copy_btn = QPushButton("COPY")
        copy_btn.setFixedHeight(20)
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {theme.TEXT_DIM}; font-size: 10px;
                letter-spacing: 0.10em; padding: 0 6px;
            }}
            QPushButton:hover {{ color: {theme.TEXT}; }}
        """)
        copy_btn.clicked.connect(self._copy)
        hl.addWidget(copy_btn)

        clear_btn = QPushButton("CLEAR")
        clear_btn.setFixedHeight(20)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {theme.TEXT_DIM}; font-size: 10px;
                letter-spacing: 0.10em; padding: 0 6px;
            }}
            QPushButton:hover {{ color: {theme.TEXT}; }}
        """)
        clear_btn.clicked.connect(self._clear)
        hl.addWidget(clear_btn)

        layout.addWidget(header)

        # Log text area
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(2000)
        self._text.setFixedHeight(200)
        self._text.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {theme.BG};
                color: {theme.TEXT};
                border: none;
                font-size: 10px;
                padding: 6px 10px;
            }}
        """)
        layout.addWidget(self._text)

        self._counts = {logging.DEBUG: 0, logging.INFO: 0,
                        logging.WARNING: 0, logging.ERROR: 0}

        handler = install_handler()
        handler.record_emitted.connect(self._on_record)

    def _on_record(self, level: int, text: str):
        color = _LEVEL_COLORS.get(level, theme.TEXT)
        escaped = (text.replace("&", "&amp;").replace("<", "&lt;")
                       .replace(">", "&gt;"))
        html = f'<span style="color:{color}; white-space:pre;">{escaped}</span>'
        self._text.appendHtml(html)

        bucket = level if level in self._counts else logging.ERROR
        self._counts[bucket] = self._counts.get(bucket, 0) + 1
        warns = self._counts.get(logging.WARNING, 0)
        errs  = self._counts.get(logging.ERROR, 0)
        parts = []
        if errs:
            parts.append(f'<span style="color:{theme.ERROR};">{errs} ERR</span>')
        if warns:
            col = _LEVEL_COLORS[logging.WARNING]
            parts.append(f'<span style="color:{col};">{warns} WARN</span>')
        self._level_lbl.setText("  ".join(parts) if parts else "")

        # Auto-scroll to bottom
        sb = self._text.verticalScrollBar()
        if sb.value() >= sb.maximum() - 20:
            self._text.moveCursor(QTextCursor.MoveOperation.End)

    def _clear(self):
        self._text.clear()
        for k in self._counts:
            self._counts[k] = 0
        self._level_lbl.setText("")

    def _copy(self):
        QGuiApplication.clipboard().setText(self._text.toPlainText())
