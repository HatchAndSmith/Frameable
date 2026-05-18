import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR  = Path.home() / ".frameable"
_LOG_FILE = _LOG_DIR / "frameable.log"
_FMT      = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup(debug: bool = False):
    global _configured
    if _configured:
        return
    _configured = True

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Rotating file handler — keeps last 3 × 2 MB logs
    fh = RotatingFileHandler(_LOG_FILE, maxBytes=2 * 1024 * 1024,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter(_FMT, datefmt=_DATE_FMT))
    root.addHandler(fh)

    # Console handler (visible when running from terminal / during dev)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("%(levelname)s  %(name)s  %(message)s"))
    root.addHandler(ch)

    # Redirect uncaught exceptions to the log file
    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        root.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = _excepthook


def get(name: str) -> logging.Logger:
    return logging.getLogger(name)
