from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Hashable

from .. import udev
from .usb_device import UsbDevice

SYSFS_USB_DEVICES = Path("/sys/bus/usb/devices")


class UsbBackendError(Exception):
    """USB devices cannot be enumerated at all (e.g. libusb is missing)."""


class PyUsbBackend:
    """Enumerates USB devices with pyusb (libusb).

    ``scan`` is cheap and does not open any device, so it is safe to call
    while a flasher is talking to one. ``describe`` is called once per newly
    connected device.

    ``library`` is the libusb library to use; by default pyusb finds it.
    """

    def __init__(self, library: str | None = None):
        self.library = library
        self._backend = None

    def scan(self) -> dict[Hashable, Any]:
        """Returns the attached devices as ``{identity: handle}``."""
        import usb.core

        if self.library is not None and self._backend is None:
            import usb.backend.libusb1

            self._backend = usb.backend.libusb1.get_backend(find_library=lambda name: self.library)
        try:
            devices = usb.core.find(find_all=True, backend=self._backend)
        except usb.core.NoBackendError as error:
            raise UsbBackendError("libusb was not found; install it to detect USB devices") from error
        if sys.platform.startswith("linux"):
            # Report a device once udev has set it up, so that a flasher
            # started as soon as it connects is allowed to open it.
            devices = [d for d in devices if udev.is_usb_device_initialized(d.bus, d.address)]
        return {(d.bus, d.address, d.idVendor, d.idProduct, d.bcdDevice): d for d in devices}

    def describe(self, handle: Any) -> UsbDevice:
        port_numbers = tuple(handle.port_numbers or ())
        device = UsbDevice(
            vendor_id=handle.idVendor,
            product_id=handle.idProduct,
            revision_bcd=handle.bcdDevice,
            bus=handle.bus or 0,
            address=handle.address or 0,
            port_numbers=port_numbers,
        )
        # Root hubs have no port path; sysfs names them usb1, usb2, ...
        sysfs_name = device.location if port_numbers else f"usb{device.bus}"
        manufacturer, product = self._strings(handle, sysfs_name)
        return UsbDevice(
            device.vendor_id,
            device.product_id,
            device.revision_bcd,
            manufacturer,
            product,
            device.bus,
            device.address,
            port_numbers,
        )

    def _strings(self, handle: Any, sysfs_name: str) -> tuple[str | None, str | None]:
        if sys.platform.startswith("linux"):
            # The kernel has already read these; unlike asking the device,
            # this needs no permissions on it.
            sysfs = SYSFS_USB_DEVICES / sysfs_name
            if sysfs.is_dir():
                return _read_sysfs(sysfs / "manufacturer"), _read_sysfs(sysfs / "product")

        import usb.util

        try:
            return _clean(handle.manufacturer), _clean(handle.product)
        except Exception:
            # No permission to open the device, or it has no string descriptors.
            return None, None
        finally:
            # Reading the strings opened the device; do not keep it open.
            usb.util.dispose_resources(handle)


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _read_sysfs(path: Path) -> str | None:
    try:
        return _clean(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
