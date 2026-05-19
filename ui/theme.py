from PySide6.QtGui import QColor, QFont, QFontDatabase

# ── Palette ────────────────────────────────────────────────────────────────
BG = "#1C1C1C"
SURFACE = "#2A2A2A"
BORDER = "#3D3D3D"
TEXT = "#E8E0D0"
TEXT_DIM = "#7A7A72"
ACCENT = "#E8601C"
GOOD = "#8DB87A"
WARN = "#C8A84B"
ERROR = "#C85A4B"
SURFACE2 = "#222222"

# ── Typography ─────────────────────────────────────────────────────────────
FONT_PRIMARY = "IBM Plex Mono"
FONT_FALLBACK = "Courier New"

_font_loaded = False


def load_fonts():
    global _font_loaded
    if _font_loaded:
        return
    # Attempt to load bundled font; silently skip if not present
    import os
    from pathlib import Path
    font_dir = Path(__file__).parent.parent / "assets" / "fonts"
    for ttf in font_dir.glob("*.ttf") if font_dir.exists() else []:
        QFontDatabase.addApplicationFont(str(ttf))
    _font_loaded = True


def font(size: int = 12, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(FONT_PRIMARY)
    if not f.exactMatch():
        f = QFont(FONT_FALLBACK)
    f.setPointSize(size)
    f.setWeight(weight)
    return f


def mono(size: int = 11) -> QFont:
    return font(size)


# ── Stylesheet ─────────────────────────────────────────────────────────────
QSS = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "{FONT_PRIMARY}", "{FONT_FALLBACK}";
    font-size: 13px;
    border: none;
    outline: none;
}}

QScrollArea {{
    background-color: {BG};
    border: none;
}}

QScrollBar:vertical {{
    background: {BG};
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    height: 0;
}}

QLineEdit {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 0;
    padding: 5px 10px;
    font-family: "{FONT_PRIMARY}", "{FONT_FALLBACK}";
    font-size: 13px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{
    border-color: {TEXT_DIM};
}}

QSpinBox {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 0;
    padding: 4px 8px;
    font-family: "{FONT_PRIMARY}", "{FONT_FALLBACK}";
    font-size: 13px;
    min-width: 70px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {BORDER};
    border: none;
    width: 16px;
}}
QSpinBox::up-arrow, QSpinBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
}}

QPushButton {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 0;
    padding: 7px 18px;
    font-family: "{FONT_PRIMARY}", "{FONT_FALLBACK}";
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}}
QPushButton:hover {{
    background-color: {BORDER};
    border-color: {TEXT_DIM};
}}
QPushButton:pressed {{
    background-color: {BG};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {SURFACE};
}}

QPushButton#run_btn {{
    background-color: {ACCENT};
    color: {BG};
    border: none;
    font-size: 13px;
    padding: 12px 44px;
    letter-spacing: 0.18em;
}}
QPushButton#run_btn:hover {{
    background-color: #F07030;
}}
QPushButton#run_btn:pressed {{
    background-color: #CC5518;
}}
QPushButton#run_btn:disabled {{
    background-color: transparent;
    color: {BORDER};
    border: 1px solid {BORDER};
}}

QPushButton#cancel_btn {{
    color: {TEXT_DIM};
    border-color: {SURFACE};
    font-size: 11px;
}}
QPushButton#cancel_btn:hover {{
    color: {TEXT};
    border-color: {BORDER};
}}

QCheckBox {{
    color: {TEXT};
    spacing: 8px;
    font-family: "{FONT_PRIMARY}", "{FONT_FALLBACK}";
    font-size: 12px;
    letter-spacing: 0.08em;
}}
QCheckBox::indicator {{
    width: 12px;
    height: 12px;
    border: 1px solid {BORDER};
    background: {SURFACE};
    border-radius: 0;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QRadioButton {{
    color: {TEXT};
    spacing: 8px;
    font-family: "{FONT_PRIMARY}", "{FONT_FALLBACK}";
    font-size: 12px;
    letter-spacing: 0.08em;
}}
QRadioButton::indicator {{
    width: 12px;
    height: 12px;
    border: 1px solid {BORDER};
    background: {SURFACE};
    border-radius: 0;
}}
QRadioButton::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QLabel {{
    background: transparent;
}}

QToolTip {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 8px;
    font-family: "{FONT_PRIMARY}", "{FONT_FALLBACK}";
    font-size: 11px;
    border-radius: 0;
}}
"""
