import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from serial.tools import list_ports

from qmk_toolbox import environment, udev
from qmk_toolbox.usb.bootloader.bootloader_device import FlashContext
from qmk_toolbox.usb.device_factory import create_device
from qmk_toolbox.usb.usb_device import UsbDevice

CATERINA = UsbDevice(0x1B4F, 0x9205, 0x0100, bus=1, address=7, port_numbers=(1, 4))
ATMEL_DFU = UsbDevice(0x03EB, 0x2FF4, 0x0000, bus=3, address=12, port_numbers=(1,))
LUFA_MS = UsbDevice(0x03EB, 0x2045, 0x0000, bus=3, address=13, port_numbers=(2,))


def port(device, vid, pid, location):
    return SimpleNamespace(device=device, vid=vid, pid=pid, location=location)


def test_data_dir_defaults_to_the_repo_common_directory(monkeypatch):
    monkeypatch.delenv("QMK_TOOLBOX_DATA_DIR", raising=False)
    assert (environment.data_dir() / "mcu-list.txt").is_file()
    assert Path(environment.data_file("reset.eep")).parts[-2:] == ("common", "reset.eep")


def test_data_dir_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("QMK_TOOLBOX_DATA_DIR", str(tmp_path))
    assert environment.data_dir() == tmp_path


@pytest.fixture
def udev_ready(monkeypatch):
    monkeypatch.setattr(udev, "is_node_initialized", lambda path: True)


def test_serial_port_is_matched_by_vid_and_pid(monkeypatch, udev_ready):
    monkeypatch.setattr(list_ports, "comports", lambda: [
        port("/dev/ttyS0", None, None, None),
        port("/dev/ttyACM0", 0x2341, 0x0036, "1-2:1.0"),
        port("/dev/ttyACM1", 0x1B4F, 0x9205, None),
    ])
    assert environment.find_serial_port(CATERINA) == "/dev/ttyACM1"


def test_serial_port_on_the_same_usb_port_wins(monkeypatch, udev_ready):
    monkeypatch.setattr(list_ports, "comports", lambda: [
        port("/dev/ttyACM0", 0x1B4F, 0x9205, "1-1.3:1.0"),
        port("/dev/ttyACM1", 0x1B4F, 0x9205, "1-1.4:1.0"),
    ])
    assert environment.find_serial_port(CATERINA) == "/dev/ttyACM1"


def test_serial_port_not_there_yet(monkeypatch):
    monkeypatch.setattr(list_ports, "comports", lambda: [])
    assert environment.find_serial_port(CATERINA) is None


def test_mount_point_is_the_volume_holding_the_lufa_files(monkeypatch, tmp_path):
    monkeypatch.setattr(environment, "mount_roots", lambda: [tmp_path / "missing", tmp_path])
    (tmp_path / "Backup").mkdir()
    (tmp_path / "Backup" / "FLASH.BIN").touch()
    assert environment.find_mount_point(CATERINA) is None

    (tmp_path / "LUFA").mkdir()
    (tmp_path / "LUFA" / "FLASH.BIN").touch()
    (tmp_path / "LUFA" / "EEPROM.BIN").touch()
    assert environment.find_mount_point(CATERINA) == str(tmp_path / "LUFA")


def test_install_hint(monkeypatch):
    monkeypatch.setattr(environment.sys, "platform", "linux")
    assert environment.install_hint("teensy_loader_cli") == "Install it with: sudo apt install teensy-loader-cli"
    assert environment.install_hint("mdloader") == (
        "Install mdloader and make sure it is on your PATH. "
        "QMK publishes builds at https://github.com/qmk/qmk_flashutils/releases"
    )
    monkeypatch.setattr(environment.sys, "platform", "darwin")
    assert environment.install_hint("dfu-programmer") == "Install it with: brew install dfu-programmer"


@pytest.fixture
def no_flashers(monkeypatch):
    monkeypatch.delenv("QMK_TOOLBOX_FLASHERS_DIR", raising=False)
    monkeypatch.setattr(environment.sys, "platform", "linux")


def test_without_bundled_flashers_the_system_ones_are_used(no_flashers):
    assert environment.flashers_dir() is None
    assert environment.tool_dirs() == []
    assert environment.avrdude_conf() is None


def test_bundled_flashers_come_first_with_their_avrdude_config(no_flashers, monkeypatch, tmp_path):
    monkeypatch.setenv("QMK_TOOLBOX_FLASHERS_DIR", str(tmp_path))
    monkeypatch.setattr(environment.sys, "platform", "darwin")
    assert environment.tool_dirs()[0] == tmp_path
    assert len(environment.tool_dirs()) == 3

    # A bundled config is only passed to the bundled avrdude.
    (tmp_path / "avrdude.conf").touch()
    assert environment.avrdude_conf() is None
    (tmp_path / "avrdude").touch()
    assert environment.avrdude_conf() == str(tmp_path / "avrdude.conf")
    assert environment.create_flash_context().avrdude_conf == str(tmp_path / "avrdude.conf")


@pytest.fixture
def udev_data(monkeypatch, tmp_path):
    data = tmp_path / "udev"
    data.mkdir()
    monkeypatch.setattr(udev, "UDEV_DATA_DIR", data)
    return data


def test_udev_initialized_devices(udev_data, tmp_path, monkeypatch):
    # Bus 3, address 12: minor (3 - 1) * 128 + 12 - 1
    assert not udev.is_usb_device_initialized(3, 12)
    (udev_data / "c189:267").touch()
    assert udev.is_usb_device_initialized(3, 12)

    assert not udev.is_node_initialized(str(tmp_path / "missing"))
    monkeypatch.setattr(udev, "UDEV_DATA_DIR", tmp_path / "no-udev")
    assert udev.is_usb_device_initialized(3, 12)


def test_serial_port_waits_for_udev_on_linux(monkeypatch, udev_data):
    monkeypatch.setattr(environment.sys, "platform", "linux")
    monkeypatch.setattr(list_ports, "comports", lambda: [port("/dev/ttyACM1", 0x1B4F, 0x9205, None)])
    ready = set()
    monkeypatch.setattr(udev, "is_node_initialized", lambda path: path in ready)
    assert environment.find_serial_port(CATERINA) is None
    ready.add("/dev/ttyACM1")
    assert environment.find_serial_port(CATERINA) == "/dev/ttyACM1"


def make_device(usb_device, serial_port=None):
    context = FlashContext(runner=None, find_serial_port=lambda device: serial_port)
    return create_device(usb_device, context)


@pytest.fixture
def nodes(monkeypatch, tmp_path):
    """Device nodes as files; the ones named in ``denied`` are not accessible."""
    monkeypatch.setattr(environment.sys, "platform", "linux")
    monkeypatch.setattr(udev, "usb_device_node", lambda bus, address: str(tmp_path / f"usb-{bus}-{address}"))
    denied = set()
    real_access = os.access
    monkeypatch.setattr(environment.os, "access", lambda path, mode: path not in denied and real_access(path, mode))
    return tmp_path, denied


def test_access_problem_for_a_usb_bootloader(nodes):
    tmp_path, denied = nodes
    device = make_device(ATMEL_DFU)
    node = str(tmp_path / "usb-3-12")
    assert environment.access_problem(device) is None  # no node: nothing to say

    open(node, "w").close()
    assert environment.access_problem(device) is None
    denied.add(node)
    problem = environment.access_problem(device)
    assert problem.startswith(f"You do not have permission to use {node}")
    assert "https://github.com/qmk/qmk_udev" in problem


def test_access_problem_for_a_serial_bootloader_checks_its_port(nodes):
    tmp_path, denied = nodes
    tty = tmp_path / "ttyACM0"
    tty.touch()
    denied.update({str(tty), str(tmp_path / "usb-1-7")})
    (tmp_path / "usb-1-7").touch()
    assert environment.access_problem(make_device(CATERINA, serial_port=None)) is None
    assert str(tty) in environment.access_problem(make_device(CATERINA, serial_port=str(tty)))


def test_access_problem_is_linux_only_and_not_for_mass_storage(nodes, monkeypatch):
    tmp_path, denied = nodes
    for name in ("usb-3-12", "usb-3-13"):
        (tmp_path / name).touch()
        denied.add(str(tmp_path / name))
    assert environment.access_problem(make_device(LUFA_MS)) is None
    monkeypatch.setattr(environment.sys, "platform", "darwin")
    assert environment.access_problem(make_device(ATMEL_DFU)) is None
