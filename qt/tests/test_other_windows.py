import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from qmk_toolbox.hid.hid_backend import HidBackendError
from qmk_toolbox.hid.hid_listener import HidListener
from qmk_toolbox.ui import key_layout
from qmk_toolbox.ui.hid_console_window import HidConsoleWindow
from qmk_toolbox.ui.key_tester_window import KeyTesterWindow
from test_hid import CONSOLE, OTHER_CONSOLE, RAW, FakeBackend, report


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# MARK: Key layout

def test_every_native_code_maps_to_a_drawn_key():
    drawn = {key.id for key in key_layout.KEYS}
    assert set(key_layout.LINUX_SCAN_CODES.values()) <= drawn
    assert set(key_layout.MACOS_VIRTUAL_KEYS.values()) <= drawn
    assert set(key_layout.WINDOWS_SCAN_CODES.values()) <= drawn
    # Linux and Windows can reach every drawn key; a Mac keyboard has no single code that is missing either.
    assert set(key_layout.LINUX_SCAN_CODES.values()) == drawn
    assert set(key_layout.MACOS_VIRTUAL_KEYS.values()) == drawn
    assert set(key_layout.WINDOWS_SCAN_CODES.values()) == drawn


def test_keys_do_not_overlap():
    keys = key_layout.KEYS
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            apart = (a.x + a.width <= b.x or b.x + b.width <= a.x or a.y + a.height <= b.y or b.y + b.height <= a.y)
            assert apart, (a.id, b.id)


def test_key_lookup_is_by_position():
    assert key_layout.key_id_for(38, 0, "linux") == "a"        # KEY_A (30) + 8
    assert key_layout.key_id_for(105, 0, "linux") == "right_ctrl"
    assert key_layout.key_id_for(0, 0x00, "darwin") == "a"
    assert key_layout.key_id_for(0, 0x3C, "darwin") == "right_shift"
    assert key_layout.key_id_for(0, 0x3F, "darwin") is None    # fn has no key on the drawn keyboard
    assert key_layout.key_id_for(0x1E, 0x41, "win32") == "a"
    assert key_layout.key_id_for(0x1D, 0, "win32") == "left_ctrl"
    assert key_layout.key_id_for(0xE01D, 0, "win32") == "right_ctrl"   # extended
    assert key_layout.key_id_for(0x45, 0, "win32") == "pause"
    assert key_layout.key_id_for(0xE045, 0, "win32") == "num_lock"
    assert key_layout.key_id_for(0x1C, 0, "win32") == "enter"
    assert key_layout.key_id_for(0xE01C, 0, "win32") == "kp_enter"
    assert key_layout.key_id_for(30, 65, "freebsd") is None


# MARK: Key tester

def key(window, type, scan_code, auto_repeat=False, qt_key=Qt.Key.Key_unknown):
    event = QKeyEvent(type, qt_key, Qt.KeyboardModifier.NoModifier, scan_code, 0, 0, "", auto_repeat)
    QApplication.sendEvent(window, event)


def test_key_tester_tracks_pressed_and_tested_keys(app):
    window = KeyTesterWindow(platform="linux")
    view = window.keyboard_view

    key(window, QEvent.Type.KeyPress, 38)
    assert (view.pressed, view.tested) == ({"a"}, {"a"})
    assert window.last_key_label.text() == "Last key: a"
    assert window.native_label.text() == "Scan code: 26   Virtual key: 00"

    key(window, QEvent.Type.KeyPress, 38, auto_repeat=True)
    key(window, QEvent.Type.KeyRelease, 38)
    assert (view.pressed, view.tested) == (set(), {"a"})

    key(window, QEvent.Type.KeyPress, 250)
    assert window.last_key_label.text() == "Last key: not on this keyboard"
    assert view.tested == {"a"}


def test_key_tester_keeps_tab_and_escape_for_itself(app):
    window = KeyTesterWindow(platform="linux")
    window.show()
    key(window, QEvent.Type.KeyPress, 23, qt_key=Qt.Key.Key_Tab)
    key(window, QEvent.Type.KeyPress, 9, qt_key=Qt.Key.Key_Escape)
    assert window.keyboard_view.pressed == {"tab", "esc"}
    assert window.isVisible()

    override = QKeyEvent(QEvent.Type.ShortcutOverride, Qt.Key.Key_O, Qt.KeyboardModifier.ControlModifier)
    override.ignore()
    QApplication.sendEvent(window, override)
    assert override.isAccepted()
    window.close()


def test_key_tester_paints(app):
    window = KeyTesterWindow(platform="linux")
    key(window, QEvent.Type.KeyPress, 38)
    key(window, QEvent.Type.KeyPress, 65)
    key(window, QEvent.Type.KeyRelease, 65)
    image = window.grab().toImage()
    colors = {image.pixelColor(x, y).name() for x in range(0, image.width(), 3) for y in range(0, image.height(), 3)}
    assert {"#ffcc00", "#34c759"} <= colors


# MARK: HID console

@pytest.fixture
def console(app):
    backend = FakeBackend()
    window = HidConsoleWindow(HidListener(backend))
    window.show()
    window._poll_timer.stop()  # the tests poll and read explicitly
    window._read_timer.stop()
    yield window, backend
    window.close()


def items(window):
    box = window.console_list_box
    return [box.itemText(i) for i in range(box.count())]


def test_console_window_lists_devices_and_shows_output(console):
    window, backend = console
    assert items(window) == []

    backend.attached = [CONSOLE, RAW]
    window.poll_devices()
    assert items(window) == ["(All connected devices)", "Maker Keyboard (FEED:6060:0001)"]
    assert window.console_list_box.currentIndex() == 0

    backend.handles[b"path-1"].reports = [report(b"hello\n")]
    window.listener.read()
    assert window.log_text_view.toPlainText().splitlines() == [
        "HID console connected: Maker Keyboard (FEED:6060:0001)",
        "Raw HID device connected: Maker Keyboard (FEED:6060:0001)",
        "> hello",
    ]

    window.clear_button.click()
    backend.attached = []
    window.poll_devices()
    assert items(window) == []
    assert window.log_text_view.toPlainText().splitlines() == [
        "HID console disconnected: Maker Keyboard (FEED:6060:0001)",
        "Raw HID device disconnected: Maker Keyboard (FEED:6060:0001)",
    ]


def test_console_window_with_two_keyboards(console):
    window, backend = console
    backend.attached = [CONSOLE, OTHER_CONSOLE]
    window.poll_devices()
    window.clear_button.click()

    backend.handles[b"path-1"].reports = [report(b"one\n")]
    backend.handles[b"path-3"].reports = [report(b"two\n"), report(b"three\n")]
    window.listener.read()
    # The second keyboard connected last, so its output needs no heading; the first one's does.
    assert window.log_text_view.toPlainText().splitlines() == ["Maker Keyboard", "> one", "Other Board", "> two", "> three"]

    window.clear_button.click()
    window.console_list_box.setCurrentIndex(2)  # only "Other Board"
    backend.handles[b"path-1"].reports = [report(b"ignored\n")]
    backend.handles[b"path-3"].reports = [report(b"shown\n")]
    window.listener.read()
    assert window.log_text_view.toPlainText().splitlines() == ["> shown"]


def test_console_window_stops_listening_when_closed(console):
    window, backend = console
    backend.attached = [CONSOLE]
    window.poll_devices()
    window.close()
    assert backend.handles[b"path-1"].closed
    assert not window._poll_timer.isActive() and not window._read_timer.isActive()

    window.show()  # reopening starts again from scratch
    assert window._poll_timer.isActive() and window._read_timer.isActive()
    assert items(window) == ["(All connected devices)", "Maker Keyboard (FEED:6060:0001)"]


def test_console_window_reports_missing_hidapi_once(console):
    window, backend = console

    def broken():
        raise HidBackendError("The hidapi Python module was not found")

    backend.enumerate = broken
    window._poll_timer.start()
    window.poll_devices()
    assert not window._poll_timer.isActive()
    assert "Cannot detect HID devices" in window.log_text_view.toPlainText()
