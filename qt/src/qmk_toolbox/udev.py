"""Whether udev has finished setting up a device (Linux).

A device appears in sysfs, and so to libusb and pyserial, before udev has run
its rules for it. Until then its device node may lack the permissions and ACLs
those rules grant, so a flasher started straight away (Auto-Flash) can fail.
"""

from __future__ import annotations

import os
from pathlib import Path

# udev writes a database entry for every device node once it has processed it.
UDEV_DATA_DIR = Path("/run/udev/data")

USB_DEVICE_MAJOR = 189


def is_initialized(major: int, minor: int) -> bool:
    if not UDEV_DATA_DIR.is_dir():
        # No udev (e.g. in a container): nothing to wait for.
        return True
    return (UDEV_DATA_DIR / f"c{major}:{minor}").exists()


def is_usb_device_initialized(bus: int, address: int) -> bool:
    # The kernel numbers /dev/bus/usb nodes this way.
    return is_initialized(USB_DEVICE_MAJOR, (bus - 1) * 128 + address - 1)


def is_node_initialized(path: str) -> bool:
    try:
        rdev = os.stat(path).st_rdev
    except OSError:
        return False
    return is_initialized(os.major(rdev), os.minor(rdev))


def usb_device_node(bus: int, address: int) -> str:
    return f"/dev/bus/usb/{bus:03d}/{address:03d}"
