import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.log import setup as setup_logging


def main():
    setup_logging(debug="--debug" in sys.argv)

    from core.log import get
    log = get("main")
    log.info("Frameable starting")

    from version import __version__
    log.info("version %s", __version__)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Frameable")
    app.setOrganizationName("HatchAndSmith")

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    log.info("UI ready")
    code = app.exec()
    log.info("Frameable exiting (code %d)", code)
    sys.exit(code)


if __name__ == "__main__":
    main()
