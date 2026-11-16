from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QFontDatabase, QPalette, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from ..message_type import MessageType

# Same colours as the macOS app's Colors.xcassets.
_LIGHT = {
    "background": "#FFFFFF",
    "default": "#1E1E1E",
    "info": "#666666",
    "error": "#E06060",
    "bootloader": "#D9994D",
    "hid": "#4D99D9",
    "hid_output": "#003359",
}
_DARK = {
    "background": "#1E1E1E",
    "default": "#FFFFFF",
    "info": "#C0C0C0",
    "error": "#F08080",
    "bootloader": "#FFFF00",
    "hid": "#87CEEB",
    "hid_output": "#F0FFFF",
}

# message type -> (prefix, prefix colour, text colour)
_STYLES = {
    MessageType.BOOTLOADER: ("", "bootloader", "bootloader"),
    MessageType.COMMAND: ("> ", "default", "default"),
    MessageType.COMMAND_ERROR: ("> ", "error", "info"),
    MessageType.COMMAND_OUTPUT: ("> ", "default", "info"),
    MessageType.ERROR: ("", "error", "error"),
    MessageType.HID: ("", "hid", "hid"),
    MessageType.HID_OUTPUT: ("> ", "hid", "hid_output"),
    MessageType.INFO: ("* ", "default", "info"),
    MessageType.USB: ("", "default", "default"),
}


class LogTextView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        # Kept so the log can be re-coloured when the system theme changes.
        self._entries: list[tuple[str, MessageType]] = []
        self._colors = _LIGHT
        self._restyling = False
        self._apply_theme()

    def log(self, message: str, type: MessageType) -> None:
        for line in message.split("\n"):
            if line:
                self._entries.append((line, type))
                self._append(line, type)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def log_bootloader(self, message: str) -> None:
        self.log(message, MessageType.BOOTLOADER)

    def log_error(self, message: str) -> None:
        self.log(message, MessageType.ERROR)

    def log_info(self, message: str) -> None:
        self.log(message, MessageType.INFO)

    def log_usb(self, message: str) -> None:
        self.log(message, MessageType.USB)

    def clear(self) -> None:
        self._entries.clear()
        super().clear()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and not self._restyling:
            self._apply_theme()

    def _apply_theme(self) -> None:
        window = self.palette().color(QPalette.ColorRole.Window)
        self._colors = _DARK if window.lightness() < 128 else _LIGHT

        self._restyling = True
        try:
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Base, QColor(self._colors["background"]))
            palette.setColor(QPalette.ColorRole.Text, QColor(self._colors["default"]))
            self.setPalette(palette)
        finally:
            self._restyling = False

        super().clear()
        for line, type in self._entries:
            self._append(line, type)

    def _append(self, line: str, type: MessageType) -> None:
        prefix, prefix_color, text_color = _STYLES[type]
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if prefix:
            cursor.insertText(prefix, self._format(prefix_color))
        cursor.insertText(line + "\n", self._format(text_color))

    def _format(self, color: str) -> QTextCharFormat:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor(self._colors[color]))
        return text_format
