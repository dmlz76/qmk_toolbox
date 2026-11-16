from __future__ import annotations

from typing import Callable, Hashable

from .hid_backend import HidApiBackend
from .hid_device import (
    CONSOLE_USAGE,
    CONSOLE_USAGE_PAGE,
    RAW_USAGE,
    RAW_USAGE_PAGE,
    HidConsoleDevice,
    HidDevice,
    HidDeviceInfo,
    RawDevice,
)


class HidListener:
    """Tracks HID console and raw HID devices, and collects console output.

    Like ``UsbListener`` there is no thread or timer in here. Call ``poll``
    about once a second to notice devices coming and going, and ``read``
    often (tens of times a second) to pick up console output. Callbacks run
    inside those calls, on the caller's thread.
    """

    def __init__(self, backend=None):
        self.backend = backend if backend is not None else HidApiBackend()
        self._devices: dict[Hashable, HidDevice] = {}
        # Interfaces that could not be opened; not retried until they reappear.
        self._failed: set[Hashable] = set()

        self.hid_device_connected: Callable[[HidDevice], None] | None = None
        self.hid_device_disconnected: Callable[[HidDevice], None] | None = None
        self.console_report_received: Callable[[HidConsoleDevice, str], None] | None = None
        self.open_failed: Callable[[HidDeviceInfo, OSError], None] | None = None

    @property
    def devices(self) -> list[HidDevice]:
        return list(self._devices.values())

    @property
    def console_devices(self) -> list[HidConsoleDevice]:
        return [d for d in self._devices.values() if isinstance(d, HidConsoleDevice)]

    def poll(self) -> None:
        """Raises ``HidBackendError`` if devices cannot be enumerated."""
        attached = {(i.path, i.usage_page, i.usage): i for i in self.backend.enumerate()}

        for key in [key for key in self._devices if key not in attached]:
            self._remove(key)
        self._failed &= attached.keys()

        for key, info in attached.items():
            if key in self._devices or key in self._failed:
                continue
            device = self._create_device(key, info)
            if device is None:
                continue
            self._devices[key] = device
            if self.hid_device_connected is not None:
                self.hid_device_connected(device)

    def read(self) -> None:
        for key, device in list(self._devices.items()):
            if isinstance(device, HidConsoleDevice) and not device.read():
                self._remove(key)

    def stop(self) -> None:
        for device in self._devices.values():
            device.close()
        self._devices.clear()
        self._failed.clear()

    def _create_device(self, key: Hashable, info: HidDeviceInfo) -> HidDevice | None:
        if (info.usage_page, info.usage) == (CONSOLE_USAGE_PAGE, CONSOLE_USAGE):
            try:
                handle = self.backend.open(info)
            except OSError as error:
                self._failed.add(key)
                if self.open_failed is not None:
                    self.open_failed(info, error)
                return None
            device = HidConsoleDevice(info, handle)
            device.report_received = self._report_received
            return device
        if (info.usage_page, info.usage) == (RAW_USAGE_PAGE, RAW_USAGE):
            return RawDevice(info)
        return None

    def _remove(self, key: Hashable) -> None:
        device = self._devices.pop(key)
        device.close()
        if self.hid_device_disconnected is not None:
            self.hid_device_disconnected(device)

    def _report_received(self, device: HidConsoleDevice, report: str) -> None:
        if self.console_report_received is not None:
            self.console_report_received(device, report)
