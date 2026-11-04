from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import theme
from .app import App


def main() -> None:
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Secret Manager")
    theme.apply(app=qt_app)
    window = App()
    window.showMaximized()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
