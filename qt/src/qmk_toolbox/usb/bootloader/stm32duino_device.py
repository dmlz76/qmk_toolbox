from ...message_type import MessageType
from .bootloader_device import BootloaderDevice
from .bootloader_type import BootloaderType


class STM32DuinoDevice(BootloaderDevice):
    name = "STM32Duino"
    type = BootloaderType.STM32DUINO

    def flash(self, mcu: str, file: str) -> None:
        if not file.lower().endswith(".bin"):
            self.print("Only firmware files in .bin format can be flashed with dfu-util!", MessageType.ERROR)
            return
        self.run_process("dfu-util", ["-a", "2", "-d", "1EAF:0003", "-R", "-D", file])

