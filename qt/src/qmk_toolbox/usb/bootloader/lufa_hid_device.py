from ..usb_device import UsbDevice
from .bootloader_device import BootloaderDevice, FlashContext
from .bootloader_type import BootloaderType


class LUFAHIDDevice(BootloaderDevice):
    # Not resettable: hid_bootloader_cli 210130 lacks the -b flag.
    # The next LUFA release should have it thanks to abcminiuser/lufa#173.

    def __init__(self, usb_device: UsbDevice, context: FlashContext):
        super().__init__(usb_device, context)
        if self.revision_bcd == 0x0936:
            self.name = "QMK HID"
            self.type = BootloaderType.QMK_HID
        else:
            self.name = "LUFA HID"
            self.type = BootloaderType.LUFA_HID

    def flash(self, mcu: str, file: str) -> None:
        self.run_process("hid_bootloader_cli", [f"-mmcu={mcu}", file, "-v"])
