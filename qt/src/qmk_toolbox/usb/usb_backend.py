from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Hashable

from .usb_device import UsbDevice

SYSFS_USB_DEVICES = Path("/sys/bus/usb/devices")


class UsbBackendError(Exception):
    """USB devices cannot be enumerated at all (e.g. libusb is missing)."""


class PyUsbBackend:
    """Enumerates USB devices with pyusb (libusb).

    ``scan`` is cheap and does not open any device, so it is safe to call
    while a flasher is talking to one. ``describe`` is called once per newly
    connected device.
    """

    def scan(self) -> dict[Hashable, Any]:
        """Returns the attached devices as ``{identity: handle}``."""
        import usb.core

        try:
            devices = usb.core.find(find_all=True)
        except usb.core.NoBackendError as error:
            raise UsbBackendError("libusb was not found; install it to detect USB devices") from error
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
        manufacturer, product = self._strings(handle, device.location)
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

    def _strings(self, handle: Any, location: str) -> tuple[str | None, str | None]:
        if sys.platform.startswith("linux"):
            # The kernel has already read these; unlike asking the device,
            # this needs no permissions on it.
            sysfs = SYSFS_USB_DEVICES / location
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
