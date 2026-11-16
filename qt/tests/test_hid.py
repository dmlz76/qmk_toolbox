import pytest

from qmk_toolbox.hid.hid_device import HidConsoleDevice, HidDeviceInfo, RawDevice
from qmk_toolbox.hid.hid_listener import HidListener

CONSOLE = HidDeviceInfo(b"path-1", 0xFEED, 0x6060, 0x0001, 0xFF31, 0x0074, "Maker", "Keyboard")
# On macOS every interface of a device can share one path, so the usage is part of the identity.
KEYBOARD = HidDeviceInfo(b"path-1", 0xFEED, 0x6060, 0x0001, 0x0001, 0x0006, "Maker", "Keyboard")
RAW = HidDeviceInfo(b"path-2", 0xFEED, 0x6060, 0x0001, 0xFF60, 0x0061, "Maker", "Keyboard")
OTHER_CONSOLE = HidDeviceInfo(b"path-3", 0xFEED, 0x1234, 0x0002, 0xFF31, 0x0074, "Other", "Board")


def report(text: bytes, size: int = 32) -> list[int]:
    return list(text.ljust(size, b"\0"))


class FakeHandle:
    def __init__(self):
        self.reports: list[list[int]] = []
        self.closed = False
        self.gone = False

    def read(self, size):
        if self.gone:
            raise OSError("read error")
        return self.reports.pop(0) if self.reports else []

    def close(self):
        self.closed = True


class FakeBackend:
    def __init__(self):
        self.attached: list[HidDeviceInfo] = []
        self.handles: dict[bytes, FakeHandle] = {}
        self.unopenable: set[bytes] = set()
        self.opened: list[bytes] = []

    def enumerate(self):
        return list(self.attached)

    def open(self, info):
        self.opened.append(info.path)
        if info.path in self.unopenable:
            raise OSError("open failed")
        self.handles[info.path] = FakeHandle()
        return self.handles[info.path]


@pytest.fixture
def hid():
    backend = FakeBackend()
    listener = HidListener(backend)
    events = []
    listener.hid_device_connected = lambda d: events.append(("+", type(d).__name__, str(d)))
    listener.hid_device_disconnected = lambda d: events.append(("-", type(d).__name__, str(d)))
    listener.console_report_received = lambda d, line: events.append(("line", d.product, line))
    listener.open_failed = lambda info, error: events.append(("open failed", info.product, str(error)))
    return listener, backend, events


def test_only_console_and_raw_interfaces_are_reported(hid):
    listener, backend, events = hid
    backend.attached = [KEYBOARD, CONSOLE, RAW]
    listener.poll()
    listener.poll()
    assert events == [
        ("+", "HidConsoleDevice", "Maker Keyboard (FEED:6060:0001)"),
        ("+", "RawDevice", "Maker Keyboard (FEED:6060:0001)"),
    ]
    assert backend.opened == [b"path-1"]  # the raw interface is not opened
    assert [type(d) for d in listener.devices] == [HidConsoleDevice, RawDevice]

    backend.attached = [KEYBOARD]
    listener.poll()
    assert [e[:2] for e in events[2:]] == [("-", "HidConsoleDevice"), ("-", "RawDevice")]
    assert backend.handles[b"path-1"].closed
    assert listener.devices == []


def test_console_lines_are_assembled_from_reports(hid):
    listener, backend, events = hid
    backend.attached = [CONSOLE]
    listener.poll()
    events.clear()

    handle = backend.handles[b"path-1"]
    handle.reports = [
        report(b"hello\n"),
        report(b"matrix scan fre"),
        report(b"quency: 1234\nKL: kc"),
        report(b": 4\n\n"),
    ]
    listener.read()
    assert events == [
        ("line", "Keyboard", "hello"),
        ("line", "Keyboard", "matrix scan frequency: 1234"),
        ("line", "Keyboard", "KL: kc: 4"),
        ("line", "Keyboard", ""),
    ]


def test_utf8_split_across_reports(hid):
    listener, backend, events = hid
    backend.attached = [CONSOLE]
    listener.poll()
    events.clear()

    text = "température: 21°C\n".encode()
    backend.handles[b"path-1"].reports = [report(text[:17]), report(text[17:])]
    listener.read()
    assert events == [("line", "Keyboard", "température: 21°C")]


def test_report_that_fills_the_buffer_without_padding(hid):
    listener, backend, events = hid
    backend.attached = [CONSOLE]
    listener.poll()
    events.clear()
    backend.handles[b"path-1"].reports = [list(b"0123456789abcdef0123456789abcde\n")]
    listener.read()
    assert events == [("line", "Keyboard", "0123456789abcdef0123456789abcde")]


def test_device_that_stops_answering_is_dropped(hid):
    listener, backend, events = hid
    backend.attached = [CONSOLE, OTHER_CONSOLE]
    listener.poll()
    events.clear()

    backend.handles[b"path-1"].gone = True
    backend.handles[b"path-3"].reports = [report(b"still here\n")]
    listener.read()
    assert events == [
        ("-", "HidConsoleDevice", "Maker Keyboard (FEED:6060:0001)"),
        ("line", "Board", "still here"),
    ]
    assert [d.product for d in listener.console_devices] == ["Board"]


def test_console_that_cannot_be_opened_is_reported_once(hid):
    listener, backend, events = hid
    backend.unopenable = {b"path-1"}
    backend.attached = [CONSOLE]
    listener.poll()
    listener.poll()
    assert events == [("open failed", "Keyboard", "open failed")]

    # Replugging it is a reason to try again.
    backend.attached = []
    listener.poll()
    backend.unopenable = set()
    backend.attached = [CONSOLE]
    listener.poll()
    assert events[-1][:2] == ("+", "HidConsoleDevice")


def test_stop_closes_the_devices(hid):
    listener, backend, _ = hid
    backend.attached = [CONSOLE]
    listener.poll()
    listener.stop()
    assert backend.handles[b"path-1"].closed
    assert listener.devices == []
