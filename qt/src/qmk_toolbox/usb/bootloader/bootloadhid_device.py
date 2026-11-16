from .bootloader_device import BootloaderDevice
from .bootloader_type import BootloaderType


class BootloadHIDDevice(BootloaderDevice):
    name = "BootloadHID"
    type = BootloaderType.BOOTLOADHID
    resettable = True

    def flash(self, mcu: str, file: str) -> None:
        self.run_process("bootloadHID", ["-r", file])

    def reset(self, mcu: str) -> None:
        self.run_process("bootloadHID", ["-r"])
