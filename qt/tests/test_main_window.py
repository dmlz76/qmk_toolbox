import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from qmk_toolbox import environment
from qmk_toolbox.ui.main_window import MainWindow
from qmk_toolbox.usb.usb_backend import UsbBackendError
from qmk_toolbox.usb.usb_device import UsbDevice
from qmk_toolbox.usb.usb_listener import UsbListener

KEYBOARD = UsbDevice(0xFEED, 0x6060, 0x0001, "Maker", "Keyboard", bus=1, address=5)
ATMEL_DFU = UsbDevice(0x03EB, 0x2FF4, 0x0000, "ATMEL", "ATm32U4DFU", bus=1, address=6)
STM32DUINO = UsbDevice(0x1EAF, 0x0003, 0x0000, "LeafLabs", "Maple", bus=1, address=7)


class FakeBackend:
    def __init__(self):
        self.attached = []
        self.error = None

    def scan(self):
        if self.error:
            raise self.error
        return {(d.bus, d.address): d for d in self.attached}

    def describe(self, handle):
        return handle


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def wait_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        QApplication.processEvents()
        time.sleep(0.005)
    QApplication.processEvents()


class Ui:
    def __init__(self, harness, tmp_path):
        self.harness = harness
        self.backend = FakeBackend()
        self.settings_path = str(tmp_path / "settings.ini")
        self.firmware = tmp_path / "fw.hex"
        self.firmware.write_text(":00000001FF\n")
        self.window = self.open()

    def open(self):
        settings = QSettings(self.settings_path, QSettings.Format.IniFormat)
        window = MainWindow(UsbListener(self.harness.context, self.backend), settings)
        window._poll_timer.stop()  # the tests poll explicitly
        return window

    def attach(self, *devices):
        self.backend.attached = list(devices)
        self.window.poll_devices()

    def log(self):
        return self.window.log_text_view.toPlainText()

    def idle(self):
        wait_until(lambda: not self.window._busy)


@pytest.fixture
def ui(app, harness, tmp_path, monkeypatch):
    # The fake devices' bus and address could name a real device node here.
    monkeypatch.setattr(environment, "access_problem", lambda device: None)
    ui = Ui(harness, tmp_path)
    yield ui
    ui.idle()
    ui.window.close()


def test_startup(ui):
    assert ui.log().startswith("* QMK Toolbox ")
    assert " - Atmel/LUFA/QMK DFU via dfu-programmer" in ui.log()
    assert ui.window.mcu_box.currentText() == "ATmega32U4"
    assert not ui.window.flash_button.isEnabled()
    assert not ui.window.reset_button.isEnabled()
    assert not ui.window.clear_eeprom_button.isEnabled()


def test_buttons_follow_the_connected_bootloaders(ui):
    ui.attach(KEYBOARD)
    assert not ui.window.flash_button.isEnabled()
    assert "USB device" not in ui.log()

    ui.attach(STM32DUINO)
    assert "STM32Duino device connected: LeafLabs Maple (1EAF:0003:0000)" in ui.log()
    assert ui.window.flash_button.isEnabled()
    assert not ui.window.reset_button.isEnabled()
    assert not ui.window.clear_eeprom_button.isEnabled()

    ui.attach(STM32DUINO, ATMEL_DFU)
    assert ui.window.reset_button.isEnabled()
    assert ui.window.clear_eeprom_button.isEnabled()
    assert ui.window.set_left_hand_action.isEnabled()

    ui.attach()
    assert "Atmel DFU device disconnected" in ui.log()
    assert not ui.window.flash_button.isEnabled()


def test_show_all_devices(ui):
    ui.window.show_all_devices_action.setChecked(True)
    ui.attach(KEYBOARD)
    ui.attach()
    assert "USB device connected: Maker Keyboard (FEED:6060:0001)" in ui.log()
    assert "USB device disconnected: Maker Keyboard (FEED:6060:0001)" in ui.log()


def test_flash_needs_a_file(ui):
    ui.attach(ATMEL_DFU)
    ui.window.flash_button.click()
    assert "Please select a file" in ui.log()

    ui.window.filepath_box.setEditText("/no/such/fw.hex")
    ui.window.flash_button.click()
    assert "File does not exist" in ui.log()
    assert ui.harness.calls == []


def test_flash(ui):
    ui.attach(ATMEL_DFU)
    ui.window.set_file_path(str(ui.firmware))
    ui.window.mcu_box.select_key("atmega32u2")
    ui.window.flash_button.click()
    ui.idle()

    assert ui.harness.calls == [
        ("dfu-programmer", ["atmega32u2", "erase", "--force"]),
        ("dfu-programmer", ["atmega32u2", "flash", "--force", str(ui.firmware)]),
        ("dfu-programmer", ["atmega32u2", "reset"]),
    ]
    log = ui.log()
    start = log.index("Attempting to flash, please don't remove device")
    command = log.index("> dfu-programmer atmega32u2 erase --force")
    assert start < command < log.index("Flash complete")
    assert ui.window.flash_button.isEnabled()


def test_ui_is_locked_while_flashing(ui):
    release = threading.Event()
    original_run = ui.harness.runner.run

    def slow_run(command, args, output, timeout=None):
        release.wait(5)
        return original_run(command, args, output, timeout)

    ui.harness.runner.run = slow_run
    ui.attach(ATMEL_DFU)
    ui.window.set_file_path(str(ui.firmware))
    ui.window.flash_button.click()

    assert not ui.window.flash_button.isEnabled()
    assert not ui.window.reset_button.isEnabled()
    ui.window.reset_all()  # ignored: one operation at a time
    ui.window.close()
    assert "Please wait for the current operation to finish" in ui.log()

    release.set()
    ui.idle()
    assert len(ui.harness.calls) == 3
    assert ui.window.flash_button.isEnabled()


def test_reset_and_eeprom(ui):
    ui.attach(ATMEL_DFU, STM32DUINO)
    ui.window.reset_button.click()
    ui.idle()
    assert ui.harness.calls == [("dfu-programmer", ["atmega32u4", "reset"])]

    ui.harness.calls.clear()
    ui.window.clear_eeprom_button.click()
    ui.idle()
    ui.window.set_handedness_all(left=True)
    ui.idle()
    ui.window.set_handedness_all(left=False)
    ui.idle()
    eeprom_files = [args[-1] for _, args in ui.harness.calls if "--eeprom" in args]
    assert eeprom_files == [environment.data_file(f) for f in ("reset.eep", "reset_left.eep", "reset_right.eep")]
    assert all(os.path.isfile(f) for f in eeprom_files)
    assert "EEPROM clear complete" in ui.log()
    assert ui.log().count("EEPROM write complete") == 2


def test_flasher_failure_is_logged_and_ui_recovers(ui):
    def broken_run(command, args, output, timeout=None):
        raise RuntimeError("boom")

    ui.harness.runner.run = broken_run
    ui.attach(ATMEL_DFU)
    ui.window.reset_button.click()
    ui.idle()
    assert "Atmel DFU: boom" in ui.log()
    assert ui.window.reset_button.isEnabled()


def test_auto_flash(ui):
    ui.window.set_file_path(str(ui.firmware))
    ui.window.auto_flash_box.setChecked(True)
    assert ui.window.auto_flash_action.isChecked()
    assert "Auto-Flash enabled" in ui.log()

    ui.attach(ATMEL_DFU)
    ui.idle()
    assert [args[1] for _, args in ui.harness.calls] == ["erase", "flash", "reset"]
    assert not ui.window.flash_button.isEnabled()

    ui.window.poll_devices()  # still attached: must not flash again
    ui.idle()
    assert len(ui.harness.calls) == 3

    ui.window.auto_flash_action.setChecked(False)
    assert not ui.window.auto_flash_box.isChecked()
    assert ui.window.flash_button.isEnabled()


def test_auto_flash_of_a_device_connecting_during_a_flash(ui):
    release = threading.Event()
    original_run = ui.harness.runner.run
    ui.harness.runner.run = lambda *a, **k: (release.wait(5), original_run(*a, **k))[1]

    ui.window.set_file_path(str(ui.firmware))
    ui.window.auto_flash_box.setChecked(True)
    ui.attach(ATMEL_DFU)
    ui.attach(ATMEL_DFU, STM32DUINO)  # arrives while the first flash is running
    release.set()
    wait_until(lambda: ui.log().count("Flash complete") == 2)
    ui.idle()
    assert ui.log().count("Attempting to flash") == 2


def test_inaccessible_bootloader_is_reported(ui, monkeypatch):
    monkeypatch.setattr(environment, "access_problem", lambda device: f"No access to {device.name}")
    ui.attach(ATMEL_DFU)
    assert "Atmel DFU device connected" in ui.log()
    assert "No access to Atmel DFU" in ui.log()
    ui.attach(ATMEL_DFU, KEYBOARD)
    assert ui.log().count("No access to") == 1


def test_missing_libusb_is_reported_once(ui):
    ui.backend.error = UsbBackendError("libusb was not found")
    ui.window._poll_timer.start()
    ui.window.poll_devices()
    assert not ui.window._poll_timer.isActive()
    assert ui.log().count("Cannot detect USB devices: libusb was not found") == 1


def test_only_firmware_files_are_accepted(ui, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("x")
    ui.window.set_file_path(str(notes))
    assert ui.window.filepath_box.currentText() == ""

    ui.window.set_file_path(str(ui.firmware))
    assert ui.window.filepath_box.currentText() == str(ui.firmware)


def test_settings_are_remembered(ui, tmp_path):
    second = tmp_path / "other.bin"
    second.write_bytes(b"x")
    ui.window.set_file_path(str(ui.firmware))
    ui.window.set_file_path(str(second))
    ui.window.set_file_path(str(ui.firmware))  # most recent again, no duplicate
    ui.window.mcu_box.select_key("at90usb1286")
    ui.window.show_all_devices_action.setChecked(True)
    ui.window.auto_flash_box.setChecked(True)
    ui.window.close()

    ui.window = ui.open()
    box = ui.window.filepath_box
    assert [box.itemText(i) for i in range(box.count())] == [str(ui.firmware), str(second)]
    assert box.currentText() == str(ui.firmware)
    assert ui.window.mcu_box.selected_key() == "at90usb1286"
    assert ui.window.show_all_devices_action.isChecked()
    assert not ui.window.auto_flash_box.isChecked()  # deliberately not remembered

    ui.window._clear_recent_files()
    assert box.count() == 0
    ui.window.close()
    ui.window = ui.open()
    assert ui.window.filepath_box.count() == 0


def test_qmk_link_is_downloaded_and_selected(ui, tmp_path, monkeypatch):
    from qmk_toolbox import firmware

    def fake_download(url, dest_dir, timeout=30.0):
        assert url == "https://example.com/fw.hex"
        return ui.firmware

    monkeypatch.setattr(firmware, "download_firmware", fake_download)
    ui.window.set_file_path("qmk://https://example.com/fw.hex")
    wait_until(lambda: "File saved to" in ui.log())
    assert "Downloading the file: https://example.com/fw.hex" in ui.log()
    assert ui.window.filepath_box.currentText() == str(ui.firmware)

    def failing_download(url, dest_dir, timeout=30.0):
        raise ValueError("Only .hex and .bin files can be downloaded")

    monkeypatch.setattr(firmware, "download_firmware", failing_download)
    ui.window.set_file_path("qmk://https://example.com/setup.exe")
    wait_until(lambda: "Could not download file" in ui.log())


def test_another_launch_selects_its_file(ui, monkeypatch):
    monkeypatch.setenv("XDG_ACTIVATION_TOKEN", "")  # restored after the test
    ui.window.present([ui.firmware.as_uri()], "token-2")
    assert ui.window.filepath_box.currentText() == str(ui.firmware)
    assert os.environ["XDG_ACTIVATION_TOKEN"] == "token-2"


def test_tools_menu_opens_the_other_windows(ui):
    ui.window.show_key_tester()
    ui.window.show_hid_console()
    key_tester, hid_console = ui.window.key_tester_window, ui.window.hid_console_window
    hid_console._poll_timer.stop()
    hid_console._read_timer.stop()
    assert key_tester.isVisible() and hid_console.isVisible()

    ui.window.show_key_tester()  # reuses the window
    assert ui.window.key_tester_window is key_tester

    ui.window.close()
    assert not key_tester.isVisible() and not hid_console.isVisible()


def test_files_and_links_opened_by_macos(ui, monkeypatch):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QFileOpenEvent

    from qmk_toolbox import firmware
    from qmk_toolbox.ui.file_open_handler import FileOpenHandler

    downloads = []
    monkeypatch.setattr(firmware, "download_firmware", lambda url, dest, timeout=30.0: downloads.append(url) or ui.firmware)

    app = QApplication.instance()
    handler = FileOpenHandler()
    app.installEventFilter(handler)
    try:
        # Before the window is ready: kept until it is.
        QApplication.sendEvent(app, QFileOpenEvent(str(ui.firmware)))
        assert ui.window.filepath_box.currentText() == ""
        handler.set_handler(lambda target: ui.window.present([target]))
        assert ui.window.filepath_box.currentText() == str(ui.firmware)

        QApplication.sendEvent(app, QFileOpenEvent(QUrl("qmk://https://example.com/my%20fw.hex")))
        wait_until(lambda: "File saved to" in ui.log())
        assert downloads == ["https://example.com/my%20fw.hex"]
    finally:
        app.removeEventFilter(handler)
