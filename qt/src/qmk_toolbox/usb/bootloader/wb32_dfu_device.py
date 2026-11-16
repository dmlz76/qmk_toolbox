from .bootloader_device import BootloaderDevice
from .bootloader_type import BootloaderType


class WB32DFUDevice(BootloaderDevice):
    name = "WB32 DFU"
    type = BootloaderType.WB32_DFU
    resettable = True

    def flash(self, mcu: str, file: str) -> None:
        if file.lower().endswith(".bin"):
            self.run_process("wb32-dfu-updater_cli", ["--toolbox-mode", "--dfuse-address", "0x08000000", "--download", file])
        else:
            self.run_process("wb32-dfu-updater_cli", ["--toolbox-mode", "--download", file])

    def reset(self, mcu: str) -> None:
        self.run_process("wb32-dfu-updater_cli", ["--reset"])
