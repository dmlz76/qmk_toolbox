from .bootloader_device import BootloaderDevice
from .bootloader_type import BootloaderType


class USBTinyISPDevice(BootloaderDevice):
    name = "USBTinyISP"
    type = BootloaderType.USBTINYISP
    eeprom_flashable = True

    def flash(self, mcu: str, file: str) -> None:
        self.run_process("avrdude", ["-p", mcu, "-c", "usbtiny", "-U", f"flash:w:{file}:i", *self.avrdude_conf_args()])

    def flash_eeprom(self, mcu: str, file: str) -> None:
        self.run_process("avrdude", ["-p", mcu, "-c", "usbtiny", "-U", f"eeprom:w:{file}:i", *self.avrdude_conf_args()])
