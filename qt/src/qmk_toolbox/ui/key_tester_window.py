from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFocusEvent, QKeyEvent, QPainter, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from . import key_layout

UNIT = 40  # pixels per key unit at the default window size
PRESSED_COLOR = QColor("#FFCC00")
TESTED_COLOR = QColor("#34C759")


class KeyboardView(QWidget):
    """Draws the keyboard: yellow while a key is held, green once it has been pressed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pressed: set[str] = set()
        self.tested: set[str] = set()
        self.setMinimumSize(int(key_layout.WIDTH * UNIT * 0.6), int(key_layout.HEIGHT * UNIT * 0.6))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(int(key_layout.WIDTH * UNIT), int(key_layout.HEIGHT * UNIT))

    def set_key(self, key_id: str, pressed: bool) -> None:
        if pressed:
            self.pressed.add(key_id)
            self.tested.add(key_id)
        else:
            self.pressed.discard(key_id)
        self.update()

    def release_all(self) -> None:
        self.pressed.clear()
        self.update()

    def paintEvent(self, event) -> None:
        unit = min(self.width() / key_layout.WIDTH, self.height() / key_layout.HEIGHT)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = painter.font()
        font.setPixelSize(max(int(unit * 0.26), 7))
        painter.setFont(font)

        text_color = self.palette().color(QPalette.ColorRole.WindowText)
        border_color = QColor(text_color)
        border_color.setAlphaF(0.45)
        idle_text_color = QColor(text_color)
        idle_text_color.setAlphaF(0.7)

        for key in key_layout.KEYS:
            rect = QRectF(key.x * unit, key.y * unit, key.width * unit, key.height * unit).adjusted(2, 2, -2, -2)
            highlighted = key.id in self.pressed or key.id in self.tested
            painter.setPen(border_color)
            if key.id in self.pressed:
                painter.setBrush(PRESSED_COLOR)
            elif key.id in self.tested:
                painter.setBrush(TESTED_COLOR)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QColor("black") if highlighted else idle_text_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, key.legend)


class KeyTesterWindow(QWidget):
    def __init__(self, parent=None, platform: str = sys.platform):
        super().__init__(parent)
        self._platform = platform
        self.setWindowTitle("Key Tester")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.keyboard_view = KeyboardView()
        self.last_key_label = QLabel("Last key: -")
        self.native_label = QLabel("Scan code: -   Virtual key: -")
        self.native_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        labels = QHBoxLayout()
        labels.addWidget(self.last_key_label)
        labels.addWidget(self.native_label, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.keyboard_view, 1)
        layout.addLayout(labels)

    def event(self, event: QEvent) -> bool:
        # Take every key for the tester: Tab must not move focus, Esc must not
        # close anything, and the app's own shortcuts must not fire.
        if event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            self._key_event(event, pressed=event.type() == QEvent.Type.KeyPress)
            return True
        return super().event(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        # The releases of keys still held go to whichever window has the focus now.
        self.keyboard_view.release_all()
        super().focusOutEvent(event)

    def _key_event(self, event: QKeyEvent, pressed: bool) -> None:
        if event.isAutoRepeat():
            return
        scan_code, virtual_key = event.nativeScanCode(), event.nativeVirtualKey()
        key_id = key_layout.key_id_for(scan_code, virtual_key, self._platform)
        self.native_label.setText(f"Scan code: {scan_code:02X}   Virtual key: {virtual_key:02X}")
        self.last_key_label.setText(f"Last key: {key_id or 'not on this keyboard'}")
        if key_id is not None:
            self.keyboard_view.set_key(key_id, pressed)
