"""What the app needs from the machine it runs on: data files, flashers, ports."""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

from .process_runner import ProcessRunner
from .usb.bootloader.bootloader_device import FlashContext
from .usb.usb_device import UsbDevice

# Flashers that can be installed from the system package manager, as
# {tool: package}. Anything not listed has to be installed by other means.
_APT_PACKAGES = {
    "avrdude": "avrdude",
    "dfu-programmer": "dfu-programmer",
    "dfu-util": "dfu-util",
    "teensy_loader_cli": "teensy-loader-cli",
}
_HOMEBREW_FORMULAE = {
    "avrdude": "avrdude",
    "dfu-programmer": "dfu-programmer",
    "dfu-util": "dfu-util",
    "teensy_loader_cli": "teensy_loader_cli",
}


def data_dir() -> Path:
    """The directory holding ``mcu-list.txt`` and the ``reset*.eep`` files."""
    override = os.environ.get("QMK_TOOLBOX_DATA_DIR")
    if override:
        return Path(override)
    packaged = Path(__file__).resolve().parent / "data"
    if packaged.is_dir():
        return packaged
    # Running from a checkout: qt/src/qmk_toolbox/ -> <repo>/common
    return Path(__file__).resolve().parents[3] / "common"


def data_file(name: str) -> str:
    return str(data_dir() / name)


def tool_dirs() -> list[Path]:
    """Extra places to look for flashers, besides ``PATH``."""
    if sys.platform == "darwin":
        # Apps started from Finder do not get the shell's PATH, so Homebrew's
        # directories have to be named explicitly.
        return [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    return []


def install_hint(tool: str) -> str:
    if sys.platform.startswith("linux") and tool in _APT_PACKAGES:
        return f"Install it with: sudo apt install {_APT_PACKAGES[tool]}"
    if sys.platform == "darwin" and tool in _HOMEBREW_FORMULAE:
        return f"Install it with: brew install {_HOMEBREW_FORMULAE[tool]}"
    return f"Install {tool} and make sure it is on your PATH."


def find_serial_port(usb_device: UsbDevice) -> str | None:
    """The serial port exposed by a USB device, if it has appeared yet."""
    from serial.tools import list_ports

    matches = [
        port
        for port in list_ports.comports()
        if port.vid == usb_device.vendor_id and port.pid == usb_device.product_id
    ]
    # With two identical boards attached, prefer the one on the same USB port.
    for port in matches:
        if port.location and port.location.split(":")[0] == usb_device.location:
            return port.device
    return matches[0].device if matches else None


def mount_roots() -> list[Path]:
    if sys.platform == "darwin":
        return [Path("/Volumes")]
    user = getpass.getuser()
    return [Path("/media") / user, Path("/run/media") / user, Path("/media"), Path("/mnt")]


def find_mount_point(usb_device: UsbDevice) -> str | None:
    """The mounted volume of a LUFA Mass Storage bootloader, if it is mounted yet.

    The volume is recognised by its contents (it always holds FLASH.BIN and
    EEPROM.BIN), not traced back to the USB device, so with two such
    bootloaders attached both resolve to the same volume.
    """
    for root in mount_roots():
        try:
            volumes = sorted(path for path in root.iterdir() if path.is_dir())
        except OSError:
            continue
        for volume in volumes:
            try:
                if (volume / "FLASH.BIN").is_file() and (volume / "EEPROM.BIN").is_file():
                    return str(volume)
            except OSError:
                continue
    return None


def create_flash_context() -> FlashContext:
    return FlashContext(
        runner=ProcessRunner(tool_dirs=tool_dirs(), cwd=data_dir(), install_hint=install_hint),
        find_serial_port=find_serial_port,
        find_mount_point=find_mount_point,
    )
