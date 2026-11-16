from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName("QMK Toolbox")
    app.setOrganizationName("QMK")
    app.setDesktopFileName("qmk-toolbox")

    window = MainWindow()
    # A firmware file or qmk: link to open, e.g. from a file manager or the browser.
    arguments = app.arguments()[1:]
    if arguments:
        window.set_file_path(arguments[0])
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
