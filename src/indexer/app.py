"""Indexer desktop app entry point."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from .ui.disclaimer import DisclaimerDialog
from .ui.main_window import MainWindow

APP_NAME = "Indexer"
ORG_NAME = "Indexer"
ASSETS = Path(__file__).resolve().parent / "assets"


def _load_stylesheet() -> str:
    qss = ASSETS / "style.qss"
    return qss.read_text(encoding="utf-8") if qss.exists() else ""


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationDisplayName(APP_NAME)

    icon_path = ASSETS / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        png = ASSETS / "icon.png"
        if png.exists():
            app.setWindowIcon(QIcon(str(png)))

    QFontDatabase.addApplicationFont(str(ASSETS / "Inter.ttf"))  # optional
    app.setStyleSheet(_load_stylesheet())

    dlg = DisclaimerDialog()
    if dlg.exec() != dlg.DialogCode.Accepted:
        return 0

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
