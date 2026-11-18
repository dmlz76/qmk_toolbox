"""What the app needs from the machine it runs on: data files, flashers, ports."""

from __future__ import annotations

import getpass
import os
import shutil
import string
import sys
from pathlib import Path

from . import udev
from .process_runner import ProcessRunner
from .usb.bootloader.bootloader_device import BootloaderDevice, FlashContext, SerialBootloaderDevice
from .usb.bootloader.lufa_ms_device import LUFAMSDevice
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
FLASHUTILS_URL = "https://github.com/qmk/qmk_flashutils/releases"
UDEV_RULES_URL = "https://github.com/qmk/qmk_udev"


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


def flashers_dir() -> Path | None:
    """The flashers bundled with an installed package, if there are any."""
    override = os.environ.get("QMK_TOOLBOX_FLASHERS_DIR")
    if override:
        return Path(override)
    bundled = Path(__file__).resolve().parent / "flashers"
    return bundled if bundled.is_dir() else None


def native_resources_dir() -> Path | None:
    """On Windows, run from a checkout: the native Windows app's flashers,
    libusb and driver installer, which Windows has no package manager for."""
    if sys.platform != "win32":
        return None
    # qt/src/qmk_toolbox/ -> <repo>/windows/QMK Toolbox/Resources
    resources = Path(__file__).resolve().parents[3] / "windows" / "QMK Toolbox" / "Resources"
    return resources if resources.is_dir() else None


def _bundled_dirs() -> list[Path]:
    return [d for d in (flashers_dir(), native_resources_dir()) if d is not None]


def tool_dirs() -> list[Path]:
    """Places to look for flashers before ``PATH``."""
    dirs = _bundled_dirs()
    if sys.platform == "darwin":
        # Apps started from Finder do not get the shell's PATH, so Homebrew's
        # directories have to be named explicitly.
        dirs += [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    return dirs


def avrdude_conf() -> str | None:
    """The config of the bundled avrdude. A system avrdude uses its own."""
    bundled = flashers_dir()
    if bundled is not None and shutil.which("avrdude", path=str(bundled)) is not None:
        conf = bundled / "avrdude.conf"
        return str(conf) if conf.is_file() else None
    native = native_resources_dir()
    if native is not None and shutil.which("avrdude", path=str(native)) is not None:
        # The native app runs its avrdude with the shared config.
        conf = data_dir() / "avrdude.conf"
        return str(conf) if conf.is_file() else None
    return None


def libusb_library() -> str | None:
    """libusb for pyusb on Windows, where nothing installs it system-wide.

    ``None`` elsewhere, and if there is none bundled: pyusb then looks for it
    itself (on ``PATH``, on Windows).
    """
    if sys.platform != "win32":
        return None
    for directory in _bundled_dirs():
        library = directory / "libusb-1.0.dll"
        if library.is_file():
            return str(library)
    return None


DRIVER_INSTALLER = "qmk_driver_installer.exe"
DRIVER_LIST = "drivers.txt"


def driver_installer() -> tuple[Path, Path] | None:
    """The native app's driver installer and its list of drivers, on Windows."""
    if sys.platform != "win32":
        return None
    for directory in _bundled_dirs():
        installer, drivers = directory / DRIVER_INSTALLER, directory / DRIVER_LIST
        if installer.is_file() and drivers.is_file():
            return installer, drivers
    return None


def run_driver_installer() -> bool:
    """Starts the driver installer as administrator (Windows asks first).

    It installs WinUSB or libusb drivers for the bootloaders in its list, as
    the native Windows app does, in a console window of its own. Returns
    whether it was started; False if it is missing or the user declined.
    """
    found = driver_installer()
    if found is None:
        return False
    installer, drivers = found
    import ctypes

    # ShellExecute returns a value greater than 32 on success.
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", str(installer), f'--all --force "{drivers}"', str(installer.parent), 1
    )
    return result > 32


def install_hint(tool: str) -> str:
    if sys.platform.startswith("linux") and tool in _APT_PACKAGES:
        return f"Install it with: sudo apt install {_APT_PACKAGES[tool]}"
    if sys.platform == "darwin" and tool in _HOMEBREW_FORMULAE:
        return f"Install it with: brew install {_HOMEBREW_FORMULAE[tool]}"
    return f"Install {tool} and make sure it is on your PATH. QMK publishes builds at {FLASHUTILS_URL}"


def find_serial_port(usb_device: UsbDevice) -> str | None:
    """The serial port exposed by a USB device, if it has appeared yet."""
    from serial.tools import list_ports

    matches = [
        port
        for port in list_ports.comports()
        if port.vid == usb_device.vendor_id and port.pid == usb_device.product_id
    ]
    if sys.platform.startswith("linux"):
        # Not until udev has set the port up: before that, opening it can fail.
        matches = [port for port in matches if udev.is_node_initialized(port.device)]
    # With two identical boards attached, prefer the one on the same USB port.
    for port in matches:
        if port.location and port.location.split(":")[0] == usb_device.location:
            return port.device
    return matches[0].device if matches else None


def mount_roots() -> list[Path]:
    """Directories whose subdirectories are mounted volumes."""
    if sys.platform == "win32":
        return []
    if sys.platform == "darwin":
        return [Path("/Volumes")]
    user = getpass.getuser()
    return [Path("/media") / user, Path("/run/media") / user, Path("/media"), Path("/mnt")]


def mount_volumes() -> list[Path]:
    volumes = []
    if sys.platform == "win32":
        # Drive letters are the volumes themselves.
        drives = os.listdrives() if hasattr(os, "listdrives") else [f"{letter}:\\" for letter in string.ascii_uppercase]
        volumes += [Path(drive) for drive in drives]
    for root in mount_roots():
        try:
            volumes += sorted(path for path in root.iterdir() if path.is_dir())
        except OSError:
            continue
    return volumes


def find_mount_point(usb_device: UsbDevice) -> str | None:
    """The mounted volume of a LUFA Mass Storage bootloader, if it is mounted yet.

    The volume is recognised by its contents (it always holds FLASH.BIN and
    EEPROM.BIN), not traced back to the USB device, so with two such
    bootloaders attached both resolve to the same volume.
    """
    for volume in mount_volumes():
        try:
            if (volume / "FLASH.BIN").is_file() and (volume / "EEPROM.BIN").is_file():
                return str(volume)
        except OSError:
            continue
    return None


def access_problem(device: BootloaderDevice) -> str | None:
    """Why a flasher would not be allowed to open this device, if it would not.

    Only on Linux, where access to devices is granted by udev rules.
    """
    if not sys.platform.startswith("linux") or isinstance(device, LUFAMSDevice):
        return None
    if isinstance(device, SerialBootloaderDevice):
        # None if the port has not appeared yet; the flasher reports that.
        node = device.serial_port
    else:
        node = udev.usb_device_node(device.usb_device.bus, device.usb_device.address)
    if node is None or not os.path.exists(node) or os.access(node, os.R_OK | os.W_OK):
        return None
    return (
        f"You do not have permission to use {node}, so flashing this device will fail. "
        f"Install QMK's udev rules ({UDEV_RULES_URL}), then reconnect the device."
    )


def create_flash_context() -> FlashContext:
    return FlashContext(
        runner=ProcessRunner(tool_dirs=tool_dirs(), cwd=data_dir(), install_hint=install_hint),
        avrdude_conf=avrdude_conf(),
        find_serial_port=find_serial_port,
        find_mount_point=find_mount_point,
    )
