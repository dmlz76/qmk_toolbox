from ...message_type import MessageType
from .bootloader_device import BootloaderDevice
from .bootloader_type import BootloaderType


class KiibohdDFUDevice(BootloaderDevice):
    name = "Kiibohd DFU"
    type = BootloaderType.KIIBOHD_DFU
    resettable = True

    def flash(self, mcu: str, file: str) -> None:
        if not file.lower().endswith(".bin"):
            self.print("Only firmware files in .bin format can be flashed with dfu-util!", MessageType.ERROR)
            return
        self.run_process("dfu-util", ["-a", "0", "-d", "1C11:B007", "-D", file])

    def reset(self, mcu: str) -> None:
        self.run_process("dfu-util", ["-a", "0", "-d", "1C11:B007", "-e"])
