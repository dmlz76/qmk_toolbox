from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow
from .ui.single_instance import SingleInstance


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName("QMK Toolbox")
    app.setOrganizationName("QMK")
    app.setDesktopFileName("qmk-toolbox")
    # Installed by the Linux package; elsewhere this is a null icon and changes nothing.
    app.setWindowIcon(QIcon.fromTheme("qmk-toolbox"))

    # A firmware file or qmk: link to open, e.g. from a file manager or the browser.
    arguments = app.arguments()[1:]
    instance = SingleInstance()
    if instance.forward(arguments):
        return 0
    instance.listen()

    window = MainWindow()
    instance.message_received.connect(window.present)
    if arguments:
        window.set_file_path(arguments[0])
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
