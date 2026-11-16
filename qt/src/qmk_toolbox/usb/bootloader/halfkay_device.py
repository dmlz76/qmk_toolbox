from .bootloader_device import BootloaderDevice
from .bootloader_type import BootloaderType


class HalfKayDevice(BootloaderDevice):
    name = "HalfKay"
    type = BootloaderType.HALFKAY
    resettable = True

    def flash(self, mcu: str, file: str) -> None:
        self.run_process("teensy_loader_cli", [f"-mmcu={mcu}", file, "-v"])

    def reset(self, mcu: str) -> None:
        self.run_process("teensy_loader_cli", [f"-mmcu={mcu}", "-bv"])
