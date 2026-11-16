from __future__ import annotations

from typing import Callable, Hashable

from ..message_type import MessageType
from .bootloader.bootloader_device import BootloaderDevice, FlashContext
from .device_factory import create_device
from .usb_backend import PyUsbBackend
from .usb_device import UsbDevice


class UsbListener:
    """Tracks attached USB devices and reports connects and disconnects.

    There is no thread or timer in here: call ``poll`` periodically (about
    once a second). Callbacks run inside ``poll``, on the caller's thread.
    """

    def __init__(self, context: FlashContext, backend=None):
        self.context = context
        self.backend = backend if backend is not None else PyUsbBackend()
        self.devices: dict[Hashable, UsbDevice | BootloaderDevice] = {}

        self.usb_device_connected: Callable[[UsbDevice], None] | None = None
        self.usb_device_disconnected: Callable[[UsbDevice], None] | None = None
        self.bootloader_device_connected: Callable[[BootloaderDevice], None] | None = None
        self.bootloader_device_disconnected: Callable[[BootloaderDevice], None] | None = None
        self.output_received: Callable[[BootloaderDevice, str, MessageType], None] | None = None

    @property
    def bootloaders(self) -> list[BootloaderDevice]:
        return [d for d in self.devices.values() if isinstance(d, BootloaderDevice)]

    def poll(self) -> None:
        """Raises ``UsbBackendError`` if devices cannot be enumerated."""
        attached = self.backend.scan()

        for key in [key for key in self.devices if key not in attached]:
            device = self.devices.pop(key)
            if isinstance(device, BootloaderDevice):
                _call(self.bootloader_device_disconnected, device)
            else:
                _call(self.usb_device_disconnected, device)

        for key, handle in attached.items():
            if key in self.devices:
                continue
            device = create_device(self.backend.describe(handle), self.context)
            self.devices[key] = device
            if isinstance(device, BootloaderDevice):
                device.output = self._output
                _call(self.bootloader_device_connected, device)
            else:
                _call(self.usb_device_connected, device)

    def stop(self) -> None:
        self.devices.clear()

    def _output(self, device: BootloaderDevice, message: str, type: MessageType) -> None:
        if self.output_received is not None:
            self.output_received(device, message, type)


def _call(callback, device) -> None:
    if callback is not None:
        callback(device)
