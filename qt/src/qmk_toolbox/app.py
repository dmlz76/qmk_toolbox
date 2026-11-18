from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import environment
from .ui.file_open_handler import FileOpenHandler
from .ui.main_window import MainWindow
from .ui.single_instance import SingleInstance


def window_icon() -> QIcon:
    # Installed by the Linux package. macOS takes the icon from the app bundle.
    icon = QIcon.fromTheme("qmk-toolbox")
    if not icon.isNull():
        return icon
    # Windows: bundled with the app, or the native app's in a checkout.
    candidates = [environment.data_dir() / "qmk-toolbox.ico"]
    native = environment.native_resources_dir()
    if native is not None:
        candidates.append(native / "output.ico")
    for candidate in candidates:
        if candidate.is_file():
            return QIcon(str(candidate))
    return icon


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    # On macOS, files and qmk: links opened from Finder, the Dock or a browser.
    file_open_handler = FileOpenHandler(app)
    app.installEventFilter(file_open_handler)
    app.setApplicationName("QMK Toolbox")
    app.setOrganizationName("QMK")
    app.setDesktopFileName("qmk-toolbox")
    app.setWindowIcon(window_icon())

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
    file_open_handler.set_handler(lambda target: window.present([target]))
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
