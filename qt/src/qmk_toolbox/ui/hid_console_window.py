from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ..hid.hid_backend import HidBackendError
from ..hid.hid_device import HidConsoleDevice, HidDevice
from ..hid.hid_listener import HidListener
from ..message_type import MessageType
from .log_text_view import LogTextView

POLL_INTERVAL_MS = 1000
READ_INTERVAL_MS = 20
ALL_DEVICES = "(All connected devices)"


class HidConsoleWindow(QWidget):
    """Shows what keyboards print to their HID console. Listens only while the window is open."""

    def __init__(self, listener: HidListener | None = None, parent=None):
        super().__init__(parent)
        self.listener = listener if listener is not None else HidListener()
        self._last_reported_device: HidConsoleDevice | None = None

        self.setWindowTitle("HID Console")
        self.console_list_box = QComboBox()
        self.console_list_box.setPlaceholderText("No HID console devices connected")
        self.clear_button = QPushButton("Clear")
        self.log_text_view = LogTextView()
        self.clear_button.clicked.connect(self.log_text_view.clear)

        top_row = QHBoxLayout()
        top_row.addWidget(self.console_list_box, 1)
        top_row.addWidget(self.clear_button)
        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.log_text_view, 1)
        self.resize(720, 420)

        self.listener.hid_device_connected = self._hid_device_connected
        self.listener.hid_device_disconnected = self._hid_device_disconnected
        self.listener.console_report_received = self._console_report_received
        self.listener.open_failed = lambda info, error: self.log_text_view.log_error(
            f"Could not open HID console {info.manufacturer or ''} {info.product or ''}: {error}"
        )

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self.poll_devices)
        self._read_timer = QTimer(self)
        self._read_timer.setInterval(READ_INTERVAL_MS)
        self._read_timer.timeout.connect(self.listener.read)

    def poll_devices(self) -> None:
        try:
            self.listener.poll()
        except HidBackendError as error:
            self._poll_timer.stop()
            self._read_timer.stop()
            self.log_text_view.log_error(f"Cannot detect HID devices: {error}")

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._poll_timer.isActive():
            self._poll_timer.start()
            self._read_timer.start()
            self.poll_devices()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._poll_timer.stop()
        self._read_timer.stop()
        self.listener.stop()
        self._last_reported_device = None
        self._update_console_list()
        super().closeEvent(event)

    def _hid_device_connected(self, device: HidDevice) -> None:
        if isinstance(device, HidConsoleDevice):
            self._last_reported_device = device
            self._update_console_list()
            self.log_text_view.log(f"HID console connected: {device}", MessageType.HID)
        else:
            self.log_text_view.log(f"Raw HID device connected: {device}", MessageType.HID)

    def _hid_device_disconnected(self, device: HidDevice) -> None:
        if isinstance(device, HidConsoleDevice):
            self._last_reported_device = None
            self._update_console_list()
            self.log_text_view.log(f"HID console disconnected: {device}", MessageType.HID)
        else:
            self.log_text_view.log(f"Raw HID device disconnected: {device}", MessageType.HID)

    def _console_report_received(self, device: HidConsoleDevice, report: str) -> None:
        selected = self.console_list_box.currentIndex()
        consoles = self.listener.console_devices
        if selected <= 0 or (selected - 1 < len(consoles) and consoles[selected - 1] is device):
            if self._last_reported_device is not device:
                # Say whose output follows, when it is not the same keyboard as before.
                self.log_text_view.log(f"{device.manufacturer or ''} {device.product or ''}", MessageType.HID)
                self._last_reported_device = device
            self.log_text_view.log(report, MessageType.HID_OUTPUT)

    def _update_console_list(self) -> None:
        selected = max(self.console_list_box.currentIndex(), 0)
        self.console_list_box.clear()
        consoles = self.listener.console_devices
        if consoles:
            self.console_list_box.addItem(ALL_DEVICES)
            self.console_list_box.addItems([str(device) for device in consoles])
            self.console_list_box.setCurrentIndex(selected if selected < self.console_list_box.count() else 0)
