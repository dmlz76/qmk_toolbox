from .bootloader_device import SerialBootloaderDevice
from .bootloader_type import BootloaderType


class CaterinaDevice(SerialBootloaderDevice):
    name = "Caterina"
    type = BootloaderType.CATERINA
    eeprom_flashable = True

    def flash(self, mcu: str, file: str) -> None:
        port = self.require_serial_port()
        if port is None:
            return
        self.run_process("avrdude", ["-p", mcu, "-c", "avr109", "-U", f"flash:w:{file}:i", "-P", port, *self.avrdude_conf_args()])

    def flash_eeprom(self, mcu: str, file: str) -> None:
        port = self.require_serial_port()
        if port is None:
            return
        self.run_process("avrdude", ["-p", mcu, "-c", "avr109", "-U", f"eeprom:w:{file}:i", "-P", port, *self.avrdude_conf_args()])
