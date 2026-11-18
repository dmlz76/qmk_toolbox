from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QObject, QUrl


class FileOpenHandler(QObject):
    """Firmware files and ``qmk:`` links that macOS asks the app to open.

    Opening a .hex file from Finder, dropping one on the Dock icon, or
    following a ``qmk:`` link in a browser reaches a Mac app as an Apple Event,
    which Qt turns into a FileOpen event on the application, not a command
    line argument. Install this as an event filter on the QApplication.
    Requests that arrive before ``set_handler`` are kept until then.
    """

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._handler: Callable[[str], None] | None = None
        self._pending: list[str] = []

    def set_handler(self, handler: Callable[[str], None]) -> None:
        self._handler = handler
        pending, self._pending = self._pending, []
        for target in pending:
            handler(target)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.FileOpen:
            return super().eventFilter(watched, event)
        url = event.url()
        if url.isLocalFile() or not url.scheme():
            target = event.file()
        else:
            # Encoded, so that spaces in a download link stay valid.
            target = url.toString(QUrl.ComponentFormattingOption.FullyEncoded)
        if target:
            if self._handler is not None:
                self._handler(target)
            else:
                self._pending.append(target)
        return True
