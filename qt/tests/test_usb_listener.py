from qmk_toolbox.message_type import MessageType
from qmk_toolbox.usb.bootloader.bootloader_device import BootloaderDevice
from qmk_toolbox.usb.usb_device import UsbDevice
from qmk_toolbox.usb.usb_listener import UsbListener

KEYBOARD = UsbDevice(0xFEED, 0x6060, 0x0001, "Maker", "Keyboard", bus=1, address=5, port_numbers=(2,))
BOOTLOADER = UsbDevice(0x03EB, 0x2FF4, 0x0000, "ATMEL", "ATm32U4DFU", bus=1, address=6, port_numbers=(2,))


class FakeBackend:
    def __init__(self):
        self.attached: list[UsbDevice] = []
        self.described: list[UsbDevice] = []

    def scan(self):
        return {(d.bus, d.address, d.vendor_id, d.product_id): d for d in self.attached}

    def describe(self, handle):
        self.described.append(handle)
        return handle


def make_listener(harness):
    backend = FakeBackend()
    listener = UsbListener(harness.context, backend)
    events = []
    listener.usb_device_connected = lambda d: events.append(("usb+", str(d)))
    listener.usb_device_disconnected = lambda d: events.append(("usb-", str(d)))
    listener.bootloader_device_connected = lambda d: events.append(("boot+", d.name))
    listener.bootloader_device_disconnected = lambda d: events.append(("boot-", d.name))
    return listener, backend, events


def test_reports_each_connect_and_disconnect_once(harness):
    listener, backend, events = make_listener(harness)

    backend.attached = [KEYBOARD]
    listener.poll()
    listener.poll()
    assert events == [("usb+", "Maker Keyboard (FEED:6060:0001)")]
    assert backend.described == [KEYBOARD]

    backend.attached = []
    listener.poll()
    listener.poll()
    assert events[1:] == [("usb-", "Maker Keyboard (FEED:6060:0001)")]
    assert listener.devices == {}


def test_keyboard_entering_bootloader_mode(harness):
    listener, backend, events = make_listener(harness)
    backend.attached = [KEYBOARD]
    listener.poll()
    events.clear()

    # Same physical port, but it re-enumerates as a different device.
    backend.attached = [BOOTLOADER]
    listener.poll()
    assert events == [("usb-", "Maker Keyboard (FEED:6060:0001)"), ("boot+", "Atmel DFU")]
    assert [b.name for b in listener.bootloaders] == ["Atmel DFU"]
    assert isinstance(listener.bootloaders[0], BootloaderDevice)

    backend.attached = [KEYBOARD]
    listener.poll()
    assert events[2:] == [("boot-", "Atmel DFU"), ("usb+", "Maker Keyboard (FEED:6060:0001)")]
    assert listener.bootloaders == []


def test_bootloader_output_is_forwarded(harness):
    listener, backend, _ = make_listener(harness)
    output = []
    listener.output_received = lambda device, message, type: output.append((device.name, message, type))
    backend.attached = [BOOTLOADER]
    listener.poll()

    listener.bootloaders[0].reset("atmega32u4")
    assert output == [("Atmel DFU", "dfu-programmer atmega32u4 reset", MessageType.COMMAND)]


def test_works_without_callbacks(harness):
    backend = FakeBackend()
    listener = UsbListener(harness.context, backend)
    backend.attached = [KEYBOARD, BOOTLOADER]
    listener.poll()
    backend.attached = []
    listener.poll()
    listener.stop()
