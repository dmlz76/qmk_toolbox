from .bootloader_device import SerialBootloaderDevice
from .bootloader_type import BootloaderType


class AtmelSAMBADevice(SerialBootloaderDevice):
    name = "Atmel SAM-BA"
    type = BootloaderType.ATMEL_SAMBA
    resettable = True

    def flash(self, mcu: str, file: str) -> None:
        port = self.require_serial_port()
        if port is None:
            return
        self.run_process("mdloader", ["-p", port, "-D", file, "--restart"])

    def reset(self, mcu: str) -> None:
        port = self.require_serial_port()
        if port is None:
            return
        self.run_process("mdloader", ["-p", port, "--restart"])
