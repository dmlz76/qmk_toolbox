from __future__ import annotations

import subprocess

import pytest

from qmk_toolbox.message_type import MessageType
from qmk_toolbox.usb.bootloader.bootloader_device import FlashContext
from qmk_toolbox.usb.device_factory import create_device
from qmk_toolbox.usb.usb_device import UsbDevice


class FakeRunner:
    """Records the commands instead of running them."""

    def __init__(self):
        self.calls: list[tuple[str, list[str]]] = []
        self.timeouts: list[float | None] = []
        self.hang = False

    def run(self, command, args, output, timeout=None):
        self.calls.append((command, args))
        self.timeouts.append(timeout)
        if self.hang and timeout is not None:
            raise subprocess.TimeoutExpired([command, *args], timeout)
        return 0


class Harness:
    def __init__(self):
        self.runner = FakeRunner()
        self.messages: list[tuple[str, MessageType]] = []
        self.serial_port: str | None = "/dev/ttyACM0"
        self.mount_point: str | None = None
        self.context = FlashContext(
            runner=self.runner,
            find_serial_port=lambda device: self.serial_port,
            find_mount_point=lambda device: self.mount_point,
        )

    def device(self, vendor_id: int, product_id: int, revision_bcd: int = 0x0100):
        usb_device = UsbDevice(vendor_id, product_id, revision_bcd, "Maker", "Board")
        device = create_device(usb_device, self.context)
        if device is not usb_device:
            device.output = lambda d, message, type: self.messages.append((message, type))
        return device

    @property
    def calls(self):
        return self.runner.calls

    def messages_of(self, type: MessageType) -> list[str]:
        return [message for message, t in self.messages if t is type]


@pytest.fixture
def harness():
    return Harness()
