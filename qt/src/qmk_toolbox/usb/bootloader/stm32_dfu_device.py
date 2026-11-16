from ...message_type import MessageType
from .bootloader_device import BootloaderDevice
from .bootloader_type import BootloaderType


class STM32DFUDevice(BootloaderDevice):
    name = "STM32 DFU"
    type = BootloaderType.STM32_DFU
    resettable = True

    def flash(self, mcu: str, file: str) -> None:
        if not file.lower().endswith(".bin"):
            self.print("Only firmware files in .bin format can be flashed with dfu-util!", MessageType.ERROR)
            return
        self.run_process("dfu-util", ["-a", "0", "-d", "0483:DF11", "-s", "0x08000000:leave", "-D", file])

    def reset(self, mcu: str) -> None:
        self.run_process("dfu-util", ["-a", "0", "-d", "0483:DF11", "-s", "0x08000000:leave"])
