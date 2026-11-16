import subprocess

from ...message_type import MessageType
from ..usb_device import UsbDevice
from .bootloader_device import BootloaderDevice, FlashContext
from .bootloader_type import BootloaderType


# dfu-programmer's reset can hang forever once the chip has left DFU (seen on
# macOS 27), even though the reset itself worked.
RESET_TIMEOUT = 5.0


class AtmelDFUDevice(BootloaderDevice):
    eeprom_flashable = True
    resettable = True

    def __init__(self, usb_device: UsbDevice, context: FlashContext):
        super().__init__(usb_device, context)
        if self.revision_bcd == 0x0936:
            self.name = "QMK DFU"
            self.type = BootloaderType.QMK_DFU
        else:
            self.name = "Atmel DFU"
            self.type = BootloaderType.ATMEL_DFU

    def flash(self, mcu: str, file: str) -> None:
        self.run_process("dfu-programmer", [mcu, "erase", "--force"])
        self.run_process("dfu-programmer", [mcu, "flash", "--force", file])
        self.reset(mcu)

    def flash_eeprom(self, mcu: str, file: str) -> None:
        if self.type is BootloaderType.ATMEL_DFU:
            self.run_process("dfu-programmer", [mcu, "erase", "--force"])
        self.run_process("dfu-programmer", [mcu, "flash", "--force", "--suppress-validation", "--eeprom", file])
        if self.type is BootloaderType.ATMEL_DFU:
            self.print("Please reflash device with firmware now", MessageType.BOOTLOADER)

    def reset(self, mcu: str) -> None:
        try:
            self.run_process("dfu-programmer", [mcu, "reset"], timeout=RESET_TIMEOUT)
        except subprocess.TimeoutExpired:
            self.print(
                f"Reset sent, but dfu-programmer did not return within {RESET_TIMEOUT:g} s; stopped it.",
                MessageType.BOOTLOADER,
            )
