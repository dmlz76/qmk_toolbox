from __future__ import annotations

import os
import shutil

from ...message_type import MessageType
from .bootloader_device import BootloaderDevice
from .bootloader_type import BootloaderType


class LUFAMSDevice(BootloaderDevice):
    name = "LUFA MS"
    type = BootloaderType.LUFA_MS

    _mount_point: str | None = None

    @property
    def mount_point(self) -> str | None:
        # The volume is mounted some time after the USB device shows up, so
        # the lookup is retried until it succeeds.
        if self._mount_point is None:
            self._mount_point = self.context.find_mount_point(self.usb_device)
        return self._mount_point

    def flash(self, mcu: str, file: str) -> None:
        if not file.lower().endswith(".bin"):
            self.print("Only firmware files in .bin format can be flashed with this bootloader!", MessageType.ERROR)
            return

        mount_point = self.mount_point
        if mount_point is None:
            self.print("Mount point not found!", MessageType.ERROR)
            return

        dest_file = os.path.join(mount_point, "FLASH.BIN")
        try:
            self.print(f"Deleting {dest_file}...", MessageType.COMMAND)
            os.remove(dest_file)
            self.print(f"Copying {file} to {dest_file}...", MessageType.COMMAND)
            shutil.copyfile(file, dest_file)
            self.print("Done, please eject drive now.", MessageType.COMMAND)
        except OSError as error:
            self.print(f"IO Error: {error}", MessageType.ERROR)

    def __str__(self) -> str:
        mount_point = self.mount_point
        return f"{super().__str__()} [{mount_point}]" if mount_point else super().__str__()
