from __future__ import annotations

import os
import threading
from importlib import metadata
from typing import Callable

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import environment, firmware
from ..mcu_list import load_mcu_list
from ..message_type import MessageType
from ..usb.bootloader.bootloader_device import BootloaderDevice
from ..usb.usb_backend import UsbBackendError
from ..usb.usb_device import UsbDevice
from ..usb.usb_listener import UsbListener
from .hid_console_window import HidConsoleWindow
from .key_tester_window import KeyTesterWindow
from .log_text_view import LogTextView
from .microcontroller_selector import MicrocontrollerSelector

POLL_INTERVAL_MS = 500
MAX_RECENT_FILES = 10

_STARTUP_MESSAGES = [
    "Supported bootloaders:",
    " - ARM DFU (APM32, Kiibohd, STM32, STM32duino) and RISC-V DFU (GD32V) via dfu-util (http://dfu-util.sourceforge.net/)",
    " - Atmel/LUFA/QMK DFU via dfu-programmer (http://dfu-programmer.github.io/)",
    " - Atmel SAM-BA (Massdrop) via Massdrop Loader (https://github.com/massdrop/mdloader)",
    " - BootloadHID (Atmel, PS2AVRGB) via bootloadHID (https://www.obdev.at/products/vusb/bootloadhid.html)",
    " - Caterina (Arduino, Pro Micro) via avrdude (http://nongnu.org/avrdude/)",
    " - HalfKay (Teensy, Ergodox EZ) via Teensy Loader (https://pjrc.com/teensy/loader_cli.html)",
    " - LUFA/QMK HID via hid_bootloader_cli (https://github.com/abcminiuser/lufa)",
    " - WB32 DFU via wb32-dfu-updater_cli (https://github.com/WestberryTech/wb32-dfu-updater)",
    " - LUFA Mass Storage",
    "Supported ISP flashers:",
    " - AVRISP (Arduino ISP)",
    " - USBasp (AVR ISP)",
    " - USBTiny (AVR Pocket)",
]


def app_version() -> str:
    try:
        return metadata.version("qmk-toolbox")
    except metadata.PackageNotFoundError:
        return "(development)"


class MainWindow(QMainWindow):
    # Emitted from worker threads; Qt delivers them on the UI thread.
    _message = Signal(str, object)
    _operation_finished = Signal(str)
    _file_downloaded = Signal(str)

    def __init__(self, listener: UsbListener | None = None, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings if settings is not None else QSettings("QMK", "QMK Toolbox")
        self.listener = listener if listener is not None else UsbListener(environment.create_flash_context())

        self._busy = False
        self._auto_flash_pending = False
        self._worker: threading.Thread | None = None
        self.key_tester_window: KeyTesterWindow | None = None
        self.hid_console_window: HidConsoleWindow | None = None

        self.setWindowTitle("QMK Toolbox")
        self.setAcceptDrops(True)
        self._build_ui()
        self._build_menus()

        self._message.connect(self.log_text_view.log)
        self._operation_finished.connect(self._on_operation_finished)
        self._file_downloaded.connect(self._on_file_downloaded)

        self._load_settings()

        self.log_text_view.log_info(f"QMK Toolbox {app_version()} (https://qmk.fm/toolbox)")
        for message in _STARTUP_MESSAGES:
            self.log_text_view.log_info(message)

        self.listener.usb_device_connected = self._usb_device_connected
        self.listener.usb_device_disconnected = self._usb_device_disconnected
        self.listener.bootloader_device_connected = self._bootloader_device_connected
        self.listener.bootloader_device_disconnected = self._bootloader_device_disconnected
        # Called from the threads reading a flasher's output.
        self.listener.output_received = lambda device, message, type: self._message.emit(message, type)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self.poll_devices)
        self._poll_timer.start()
        self.poll_devices()
        self._update_ui()

    # MARK: Construction

    def _build_ui(self) -> None:
        self.filepath_box = QComboBox()
        self.filepath_box.setEditable(True)
        self.filepath_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.filepath_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.filepath_box.setMinimumContentsLength(20)
        self.filepath_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.filepath_box.lineEdit().setPlaceholderText("Click Open or drag to window to select file")

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self.open_file_dialog)

        self.mcu_box = MicrocontrollerSelector(load_mcu_list(environment.data_file("mcu-list.txt")))
        self.mcu_box.currentIndexChanged.connect(
            lambda: self.settings.setValue("Microcontroller", self.mcu_box.selected_key())
        )

        file_row = QHBoxLayout()
        file_row.addWidget(self.filepath_box, 1)
        file_row.addWidget(self.open_button)
        file_row.addWidget(self.mcu_box)
        file_group = QGroupBox("Local file")
        file_group.setLayout(file_row)

        self.log_text_view = LogTextView()
        self.log_text_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_text_view.customContextMenuRequested.connect(self._show_log_menu)

        self.flash_button = QPushButton("Flash")
        self.flash_button.clicked.connect(self.flash_all)
        self.clear_eeprom_button = QPushButton("Clear EEPROM")
        self.clear_eeprom_button.clicked.connect(self.clear_eeprom_all)
        self.reset_button = QPushButton("Exit DFU")
        self.reset_button.clicked.connect(self.reset_all)
        self.auto_flash_box = QCheckBox("Auto-Flash")

        button_row = QHBoxLayout()
        button_row.addWidget(self.auto_flash_box)
        button_row.addStretch(1)
        button_row.addWidget(self.reset_button)
        button_row.addWidget(self.clear_eeprom_button)
        button_row.addWidget(self.flash_button)

        layout = QVBoxLayout()
        layout.addWidget(file_group)
        layout.addWidget(self.log_text_view, 1)
        layout.addLayout(button_row)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.resize(820, 560)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = file_menu.addAction("&Open…", self.open_file_dialog)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.recent_menu = file_menu.addMenu("Open &Recent")
        file_menu.addSeparator()
        quit_action = file_menu.addAction("&Quit", self.close)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)

        tools_menu = self.menuBar().addMenu("&Tools")
        self.flash_action = tools_menu.addAction("&Flash", self.flash_all)
        self.flash_action.setShortcut("Ctrl+Shift+F")
        eeprom_menu = tools_menu.addMenu("&EEPROM")
        self.clear_eeprom_action = eeprom_menu.addAction("&Clear", self.clear_eeprom_all)
        self.clear_eeprom_action.setShortcut("Ctrl+Shift+E")
        self.set_left_hand_action = eeprom_menu.addAction("Set &Left Hand", lambda: self.set_handedness_all(left=True))
        self.set_right_hand_action = eeprom_menu.addAction(
            "Set &Right Hand", lambda: self.set_handedness_all(left=False)
        )
        self.reset_action = tools_menu.addAction("E&xit DFU", self.reset_all)
        self.reset_action.setShortcut("Ctrl+Shift+X")
        tools_menu.addSeparator()
        self.auto_flash_action = tools_menu.addAction("&Auto-Flash")
        self.auto_flash_action.setCheckable(True)
        self.show_all_devices_action = tools_menu.addAction("Show All &Devices")
        self.show_all_devices_action.setCheckable(True)

        # The checkbox and the menu item are two views of the same setting.
        self.auto_flash_action.toggled.connect(self.auto_flash_box.setChecked)
        self.auto_flash_box.toggled.connect(self.auto_flash_action.setChecked)
        self.auto_flash_box.toggled.connect(self._auto_flash_changed)
        self.show_all_devices_action.toggled.connect(
            lambda enabled: self.settings.setValue("ShowAllDevices", enabled)
        )

        tools_menu.addSeparator()
        tools_menu.addAction("&Key Tester", self.show_key_tester)
        tools_menu.addAction("&HID Console", self.show_hid_console)

        help_menu = self.menuBar().addMenu("&Help")
        about_action = help_menu.addAction("&About QMK Toolbox", self._show_about)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)

    def _load_settings(self) -> None:
        geometry = self.settings.value("Geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self.mcu_box.select_key(str(self.settings.value("Microcontroller", "")))
        self.show_all_devices_action.setChecked(self.settings.value("ShowAllDevices", False, type=bool))

        for path in self._recent_files():
            self.filepath_box.addItem(path)
        self.filepath_box.setCurrentIndex(0 if self.filepath_box.count() else -1)
        self._rebuild_recent_menu()

    # MARK: USB devices and bootloaders

    @property
    def auto_flash_enabled(self) -> bool:
        return self.auto_flash_box.isChecked()

    def poll_devices(self) -> None:
        try:
            self.listener.poll()
        except UsbBackendError as error:
            # Nothing will change by asking again every half second.
            self._poll_timer.stop()
            self.log_text_view.log_error(f"Cannot detect USB devices: {error}")

    def _bootloader_device_connected(self, device: BootloaderDevice) -> None:
        self.log_text_view.log_bootloader(f"{device.name} device connected: {device}")
        if self.auto_flash_enabled:
            if self._busy:
                self._auto_flash_pending = True
            else:
                self.flash_all()
        else:
            self._update_ui()

    def _bootloader_device_disconnected(self, device: BootloaderDevice) -> None:
        self.log_text_view.log_bootloader(f"{device.name} device disconnected: {device}")
        self._update_ui()

    def _usb_device_connected(self, device: UsbDevice) -> None:
        if self.show_all_devices_action.isChecked():
            self.log_text_view.log_usb(f"USB device connected: {device}")

    def _usb_device_disconnected(self, device: UsbDevice) -> None:
        if self.show_all_devices_action.isChecked():
            self.log_text_view.log_usb(f"USB device disconnected: {device}")

    # MARK: Flashing

    def flash_all(self) -> None:
        file = self.filepath_box.currentText().strip()
        if not file:
            self.log_text_view.log_error("Please select a file")
            return
        if not os.path.isfile(file):
            self.log_text_view.log_error("File does not exist")
            return
        mcu = self.mcu_box.selected_key()
        self._run_operation(
            lambda device: device.flash(mcu, file),
            start="Attempting to flash, please don't remove device",
            end="Flash complete",
        )

    def reset_all(self) -> None:
        mcu = self.mcu_box.selected_key()
        self._run_operation(lambda device: device.reset(mcu), only=lambda device: device.resettable)

    def clear_eeprom_all(self) -> None:
        self._flash_eeprom_all("reset.eep", "Attempting to clear EEPROM, please don't remove device", "EEPROM clear complete")

    def set_handedness_all(self, left: bool) -> None:
        self._flash_eeprom_all(
            "reset_left.eep" if left else "reset_right.eep",
            "Attempting to set handedness, please don't remove device",
            "EEPROM write complete",
        )

    def _flash_eeprom_all(self, eeprom_file: str, start: str, end: str) -> None:
        mcu = self.mcu_box.selected_key()
        file = environment.data_file(eeprom_file)
        self._run_operation(
            lambda device: device.flash_eeprom(mcu, file),
            only=lambda device: device.eeprom_flashable,
            start=start,
            end=end,
        )

    def _run_operation(
        self,
        action: Callable[[BootloaderDevice], None],
        only: Callable[[BootloaderDevice], bool] = lambda device: True,
        start: str = "",
        end: str = "",
    ) -> None:
        """Apply ``action`` to the connected bootloaders on a worker thread, one operation at a time."""
        if self._busy:
            return
        devices = [device for device in self.listener.bootloaders if only(device)]

        self._busy = True
        self._update_ui()
        if start:
            self.log_text_view.log_bootloader(start)

        def work() -> None:
            try:
                for device in devices:
                    try:
                        action(device)
                    except Exception as error:  # a flasher problem must not take the app down
                        self._message.emit(f"{device.name}: {error}", MessageType.ERROR)
            finally:
                self._operation_finished.emit(end)

        self._worker = threading.Thread(target=work, name="flash")
        self._worker.start()

    def _on_operation_finished(self, end: str) -> None:
        if end:
            self.log_text_view.log_bootloader(end)
        self._busy = False
        self._update_ui()

        if self._auto_flash_pending:
            self._auto_flash_pending = False
            if self.auto_flash_enabled and self.listener.bootloaders:
                self.flash_all()

    def _auto_flash_changed(self, enabled: bool) -> None:
        self.log_text_view.log_info(f"Auto-Flash {'enabled' if enabled else 'disabled'}")
        self._update_ui()

    def _update_ui(self) -> None:
        # With Auto-Flash on, flashing is driven by devices connecting, not by the buttons.
        idle = not self._busy and not self.auto_flash_enabled
        bootloaders = self.listener.bootloaders
        can_flash = idle and bool(bootloaders)
        can_reset = idle and any(device.resettable for device in bootloaders)
        can_clear_eeprom = idle and any(device.eeprom_flashable for device in bootloaders)

        for widget in (self.flash_button, self.flash_action):
            widget.setEnabled(can_flash)
        for widget in (self.reset_button, self.reset_action):
            widget.setEnabled(can_reset)
        for widget in (
            self.clear_eeprom_button,
            self.clear_eeprom_action,
            self.set_left_hand_action,
            self.set_right_hand_action,
        ):
            widget.setEnabled(can_clear_eeprom)

    # MARK: Firmware file

    def open_file_dialog(self) -> None:
        current = self.filepath_box.currentText().strip()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select firmware to load",
            os.path.dirname(current) if current else "",
            "Firmware (*.hex *.bin)",
        )
        if path:
            self.set_file_path(path)

    def set_file_path(self, path: str) -> None:
        """Select a local firmware file, or download the one a ``qmk:`` link points to."""
        url = firmware.unwrap_qmk_url(path)
        if url is not None:
            self._download_file(url)
        elif firmware.is_firmware_file(path):
            self._load_local_file(os.path.abspath(path))

    def _load_local_file(self, path: str) -> None:
        recent = [path] + [p for p in self._recent_files() if p != path]
        self.settings.setValue("RecentFiles", recent[:MAX_RECENT_FILES])

        index = self.filepath_box.findText(path)
        if index < 0:
            self.filepath_box.addItem(path)
            index = self.filepath_box.count() - 1
        self.filepath_box.setCurrentIndex(index)
        self._rebuild_recent_menu()

    def _download_file(self, url: str) -> None:
        self.log_text_view.log_info(f"Downloading the file: {url}")
        downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)

        def work() -> None:
            try:
                path = firmware.download_firmware(url, downloads)
            except (OSError, ValueError) as error:
                self._message.emit(f"Could not download file: {error}", MessageType.ERROR)
            else:
                self._file_downloaded.emit(str(path))

        threading.Thread(target=work, name="download", daemon=True).start()

    def _on_file_downloaded(self, path: str) -> None:
        self.log_text_view.log_info(f"File saved to: {path}")
        self._load_local_file(path)

    def _recent_files(self) -> list[str]:
        value = self.settings.value("RecentFiles", [])
        if isinstance(value, str):  # QSettings returns a one-item list as a plain string
            value = [value]
        return [str(path) for path in value or []]

    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.clear()
        for path in self._recent_files():
            self.recent_menu.addAction(path, lambda path=path: self.set_file_path(path))
        self.recent_menu.addSeparator()
        clear_action = self.recent_menu.addAction("Clear Menu", self._clear_recent_files)
        clear_action.setEnabled(bool(self._recent_files()))

    def _clear_recent_files(self) -> None:
        self.settings.remove("RecentFiles")
        self.filepath_box.clear()
        self.filepath_box.setEditText("")
        self._rebuild_recent_menu()

    # MARK: Other windows

    def show_key_tester(self) -> None:
        if self.key_tester_window is None:
            self.key_tester_window = KeyTesterWindow()
        _bring_to_front(self.key_tester_window)

    def show_hid_console(self) -> None:
        if self.hid_console_window is None:
            self.hid_console_window = HidConsoleWindow()
        _bring_to_front(self.hid_console_window)

    # MARK: Window events

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile() and firmware.is_firmware_file(urls[0].toLocalFile()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.set_file_path(event.mimeData().urls()[0].toLocalFile())
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy:
            # Quitting would leave the flasher running with nobody watching it.
            self.log_text_view.log_error("Please wait for the current operation to finish before closing")
            event.ignore()
            return
        self._poll_timer.stop()
        self.listener.stop()
        self.settings.setValue("Geometry", self.saveGeometry())
        # They are separate top-level windows; closing the main one ends the app.
        for window in (self.key_tester_window, self.hid_console_window):
            if window is not None:
                window.close()
        event.accept()

    def _show_log_menu(self, position) -> None:
        menu = self.log_text_view.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction("Clear", self.log_text_view.clear)
        menu.exec(self.log_text_view.mapToGlobal(position))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About QMK Toolbox",
            f"<b>QMK Toolbox {app_version()}</b>"
            "<p>A flashing/debug utility for devices running QMK Firmware.</p>"
            '<p><a href="https://qmk.fm/toolbox">https://qmk.fm/toolbox</a></p>',
        )


def _bring_to_front(window: QWidget) -> None:
    window.show()
    window.raise_()
    window.activateWindow()
