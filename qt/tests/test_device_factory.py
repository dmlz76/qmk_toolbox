import re
from pathlib import Path

import pytest

from qmk_toolbox.usb.bootloader.bootloader_device import BootloaderDevice
from qmk_toolbox.usb.bootloader.bootloader_type import BootloaderType as T
from qmk_toolbox.usb.device_factory import _DEVICE_CLASSES, _DEVICE_TYPES, device_type
from qmk_toolbox.usb.usb_device import UsbDevice

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "vid, pid, rev, expected",
    [
        (0x03EB, 0x2FF4, 0x0000, T.ATMEL_DFU),
        (0x03EB, 0x2FF4, 0x0936, T.QMK_DFU),
        (0x03EB, 0x2067, 0x0001, T.LUFA_HID),
        (0x03EB, 0x2067, 0x0936, T.QMK_HID),
        (0x03EB, 0x2045, 0x0936, T.LUFA_MS),
        (0x03EB, 0x6124, 0x0000, T.ATMEL_SAMBA),
        (0x0483, 0xDF11, 0x2200, T.STM32_DFU),
        (0x0483, 0xDF11, 0x0936, T.STM32_DFU),
        (0x16C0, 0x0478, 0x0000, T.HALFKAY),
        (0x16C0, 0x0483, 0x0000, T.AVR_ISP),
        (0x16C0, 0x05DC, 0x0000, T.USBASP),
        (0x16C0, 0x05DF, 0x0000, T.BOOTLOADHID),
        (0x1781, 0x0C9F, 0x0000, T.USBTINYISP),
        (0x1B4F, 0x9205, 0x0000, T.CATERINA),
        (0x2341, 0x0036, 0x0000, T.CATERINA),
        (0x2A03, 0x0040, 0x0000, T.CATERINA),
        (0x1C11, 0xB007, 0x0000, T.KIIBOHD_DFU),
        (0x1EAF, 0x0003, 0x0000, T.STM32DUINO),
        (0x28E9, 0x0189, 0x0000, T.GD32V_DFU),
        (0x314B, 0x0106, 0x0000, T.APM32_DFU),
        (0x342D, 0xDFA0, 0x0000, T.WB32_DFU),
        (0x03EB, 0x0001, 0x0000, T.NONE),
        (0xFEED, 0x6060, 0x0001, T.NONE),
    ],
)
def test_device_type(vid, pid, rev, expected):
    assert device_type(vid, pid, rev) is expected


def test_every_bootloader_type_has_a_class():
    assert set(_DEVICE_CLASSES) == set(T) - {T.NONE}


def test_created_device_reports_the_detected_type(harness):
    for (vid, pid), _ in _DEVICE_TYPES.items():
        for rev in (0x0000, 0x0936):
            device = harness.device(vid, pid, rev)
            assert isinstance(device, BootloaderDevice)
            assert device.type is device_type(vid, pid, rev)
            assert device.name


def test_unknown_device_is_returned_unchanged(harness):
    device = harness.device(0xFEED, 0x6060)
    assert isinstance(device, UsbDevice)


def test_vid_pid_table_matches_the_macos_app():
    """The table is maintained by hand in three places; catch drift from the Swift one."""
    swift = (REPO_ROOT / "macos/QMK Toolbox/USB/USBListener.swift").read_text()
    body = swift[swift.index("func deviceType(") :]

    swift_ids = set()
    vendor = None
    for line in body.splitlines():
        code = line.split("//")[0]
        if match := re.search(r"case (0x[0-9A-F]{4}):\s*$", code) if code.startswith("        case") else None:
            vendor = int(match.group(1), 16)
        elif "productID ==" in code:
            swift_ids.add((vendor, int(re.search(r"productID == (0x[0-9A-F]{4})", code).group(1), 16)))
        elif code.strip().startswith("case 0x"):
            for pid in re.findall(r"0x[0-9A-F]{4}", code):
                swift_ids.add((vendor, int(pid, 16)))

    assert swift_ids == set(_DEVICE_TYPES)
