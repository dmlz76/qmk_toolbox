from __future__ import annotations

import sys
from typing import Any

from .hid_device import HidDeviceInfo


class HidBackendError(Exception):
    """HID devices cannot be enumerated at all (e.g. hidapi is missing)."""


def _load_hidapi():
    names = ["hid"]
    if sys.platform.startswith("linux"):
        # On Linux the "hid" module of cython-hidapi talks to devices through
        # libusb, which detaches the keyboard from the kernel while open.
        # "hidraw" is the same API on top of the kernel's hidraw interface.
        names.insert(0, "hidraw")
    for name in names:
        try:
            return __import__(name)
        except ImportError:
            continue
    raise HidBackendError("The hidapi Python module was not found; install it to use the HID console")


class HidApiBackend:
    """Enumerates and opens HID devices with hidapi (the cython-hidapi module)."""

    def __init__(self):
        self._hid = None

    def _module(self):
        if self._hid is None:
            self._hid = _load_hidapi()
        return self._hid

    def enumerate(self) -> list[HidDeviceInfo]:
        try:
            devices = self._module().enumerate()
        except OSError as error:
            raise HidBackendError(str(error)) from error
        return [
            HidDeviceInfo(
                path=d["path"],
                vendor_id=d["vendor_id"],
                product_id=d["product_id"],
                revision_bcd=d["release_number"],
                usage_page=d["usage_page"],
                usage=d["usage"],
                manufacturer=(d.get("manufacturer_string") or "").strip() or None,
                product=(d.get("product_string") or "").strip() or None,
            )
            for d in devices
        ]

    def open(self, info: HidDeviceInfo) -> Any:
        """Open a device for non-blocking reads. Raises ``OSError`` if it cannot be opened."""
        handle = self._module().device()
        handle.open_path(info.path)
        handle.set_nonblocking(1)
        return handle
