from .bootloader_device import BootloaderDevice
from .bootloader_type import BootloaderType


class USBAspDevice(BootloaderDevice):
    name = "USBasp"
    type = BootloaderType.USBASP
    eeprom_flashable = True

    def flash(self, mcu: str, file: str) -> None:
        self.run_process("avrdude", ["-p", mcu, "-c", "usbasp", "-U", f"flash:w:{file}:i", *self.avrdude_conf_args()])

    def flash_eeprom(self, mcu: str, file: str) -> None:
        self.run_process("avrdude", ["-p", mcu, "-c", "usbasp", "-U", f"eeprom:w:{file}:i", *self.avrdude_conf_args()])
