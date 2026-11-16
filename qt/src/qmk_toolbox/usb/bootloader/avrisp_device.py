from .bootloader_device import SerialBootloaderDevice
from .bootloader_type import BootloaderType


class AVRISPDevice(SerialBootloaderDevice):
    name = "AVR ISP"
    type = BootloaderType.AVR_ISP
    eeprom_flashable = True

    def flash(self, mcu: str, file: str) -> None:
        port = self.require_serial_port()
        if port is None:
            return
        self.run_process("avrdude", ["-p", mcu, "-c", "avrisp", "-U", f"flash:w:{file}:i", "-P", port, *self.avrdude_conf_args()])

    def flash_eeprom(self, mcu: str, file: str) -> None:
        port = self.require_serial_port()
        if port is None:
            return
        self.run_process("avrdude", ["-p", mcu, "-c", "avrisp", "-U", f"eeprom:w:{file}:i", "-P", port, *self.avrdude_conf_args()])
