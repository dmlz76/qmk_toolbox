from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ...message_type import MessageType
from ...process_runner import ProcessRunner
from ..usb_device import UsbDevice
from .bootloader_type import BootloaderType


def _not_found(usb_device: UsbDevice) -> str | None:
    return None


@dataclass
class FlashContext:
    """What a bootloader device needs from the platform in order to flash."""

    runner: ProcessRunner
    # Passed to avrdude with -C when set; leave unset to use avrdude's own config.
    avrdude_conf: str | None = None
    find_serial_port: Callable[[UsbDevice], str | None] = _not_found
    find_mount_point: Callable[[UsbDevice], str | None] = _not_found


class BootloaderDevice:
    name: str = ""
    type: BootloaderType = BootloaderType.NONE
    eeprom_flashable: bool = False
    resettable: bool = False

    def __init__(self, usb_device: UsbDevice, context: FlashContext):
        self.usb_device = usb_device
        self.context = context
        # Receives (device, message, type) for everything the device logs.
        self.output: Callable[[BootloaderDevice, str, MessageType], None] | None = None

    @property
    def manufacturer(self) -> str | None:
        return self.usb_device.manufacturer

    @property
    def product(self) -> str | None:
        return self.usb_device.product

    @property
    def vendor_id(self) -> int:
        return self.usb_device.vendor_id

    @property
    def product_id(self) -> int:
        return self.usb_device.product_id

    @property
    def revision_bcd(self) -> int:
        return self.usb_device.revision_bcd

    def flash(self, mcu: str, file: str) -> None:
        pass

    def flash_eeprom(self, mcu: str, file: str) -> None:
        pass

    def reset(self, mcu: str) -> None:
        pass

    def run_process(self, command: str, args: list[str], timeout: float | None = None) -> int | None:
        """Runs a flasher. Raises ``subprocess.TimeoutExpired`` if ``timeout`` (seconds) is exceeded."""
        self.print(f"{command} {' '.join(args)}", MessageType.COMMAND)
        return self.context.runner.run(command, args, self.print, timeout=timeout)

    def print(self, message: str, type: MessageType) -> None:
        if self.output is not None:
            self.output(self, message, type)

    def avrdude_conf_args(self) -> list[str]:
        conf = self.context.avrdude_conf
        return ["-C", conf] if conf else []

    def __str__(self) -> str:
        return str(self.usb_device)


class SerialBootloaderDevice(BootloaderDevice):
    """A bootloader that is flashed through a serial port.

    The port can show up a moment after the USB device does, so it is looked
    up lazily and the lookup is retried until it succeeds.
    """

    _serial_port: str | None = None

    @property
    def serial_port(self) -> str | None:
        if self._serial_port is None:
            self._serial_port = self.context.find_serial_port(self.usb_device)
        return self._serial_port

    def require_serial_port(self) -> str | None:
        port = self.serial_port
        if port is None:
            self.print("Serial port not found!", MessageType.ERROR)
        return port

    def __str__(self) -> str:
        port = self.serial_port
        return f"{super().__str__()} [{port}]" if port else super().__str__()
