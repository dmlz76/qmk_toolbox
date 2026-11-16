from types import SimpleNamespace

from serial.tools import list_ports

from qmk_toolbox import environment
from qmk_toolbox.usb.usb_device import UsbDevice

CATERINA = UsbDevice(0x1B4F, 0x9205, 0x0100, bus=1, address=7, port_numbers=(1, 4))


def port(device, vid, pid, location):
    return SimpleNamespace(device=device, vid=vid, pid=pid, location=location)


def test_data_dir_defaults_to_the_repo_common_directory(monkeypatch):
    monkeypatch.delenv("QMK_TOOLBOX_DATA_DIR", raising=False)
    assert (environment.data_dir() / "mcu-list.txt").is_file()
    assert environment.data_file("reset.eep").endswith("/common/reset.eep")


def test_data_dir_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("QMK_TOOLBOX_DATA_DIR", str(tmp_path))
    assert environment.data_dir() == tmp_path


def test_serial_port_is_matched_by_vid_and_pid(monkeypatch):
    monkeypatch.setattr(list_ports, "comports", lambda: [
        port("/dev/ttyS0", None, None, None),
        port("/dev/ttyACM0", 0x2341, 0x0036, "1-2:1.0"),
        port("/dev/ttyACM1", 0x1B4F, 0x9205, None),
    ])
    assert environment.find_serial_port(CATERINA) == "/dev/ttyACM1"


def test_serial_port_on_the_same_usb_port_wins(monkeypatch):
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
    assert environment.install_hint("mdloader") == "Install mdloader and make sure it is on your PATH."
    monkeypatch.setattr(environment.sys, "platform", "darwin")
    assert environment.install_hint("dfu-programmer") == "Install it with: brew install dfu-programmer"
