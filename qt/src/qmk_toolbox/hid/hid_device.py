from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

CONSOLE_USAGE_PAGE = 0xFF31
CONSOLE_USAGE = 0x0074
RAW_USAGE_PAGE = 0xFF60
RAW_USAGE = 0x0061

# Console reports are 32 bytes; ask for more in case a keyboard uses bigger ones.
MAX_REPORT_SIZE = 256
# Upper bound on reports handled per call, so a chatty keyboard cannot stall the caller.
MAX_REPORTS_PER_READ = 256


@dataclass(frozen=True)
class HidDeviceInfo:
    """One HID interface, as reported by the backend."""

    path: bytes
    vendor_id: int
    product_id: int
    revision_bcd: int
    usage_page: int
    usage: int
    manufacturer: str | None = None
    product: str | None = None


class HidDevice:
    def __init__(self, info: HidDeviceInfo):
        self.info = info

    @property
    def manufacturer(self) -> str | None:
        return self.info.manufacturer

    @property
    def product(self) -> str | None:
        return self.info.product

    def close(self) -> None:
        pass

    def __str__(self) -> str:
        return "%s %s (%04X:%04X:%04X)" % (
            self.info.manufacturer or "",
            self.info.product or "",
            self.info.vendor_id,
            self.info.product_id,
            self.info.revision_bcd,
        )


class RawDevice(HidDevice):
    """A raw HID interface. Only its presence is reported; it is never opened."""


class HidConsoleDevice(HidDevice):
    """A QMK console (``hid_listen`` compatible): text sent in fixed-size, NUL-padded reports."""

    def __init__(self, info: HidDeviceInfo, handle: Any):
        super().__init__(info)
        self._handle = handle
        self._current_line = bytearray()
        self.report_received: Callable[[HidConsoleDevice, str], None] | None = None

    def read(self) -> bool:
        """Handle the reports that have arrived. Returns ``False`` once the device has gone away."""
        try:
            for _ in range(MAX_REPORTS_PER_READ):
                report = self._handle.read(MAX_REPORT_SIZE)
                if not report:
                    break
                self.handle_report(bytes(report))
        except (OSError, ValueError):
            return False
        return True

    def handle_report(self, report: bytes) -> None:
        # The text ends at the first NUL; the rest of the report is padding.
        self._current_line += report.split(b"\0", 1)[0]
        # Decode whole lines only, as a UTF-8 sequence can be split across reports.
        while (line_end := self._current_line.find(b"\n")) >= 0:
            line = self._current_line[:line_end].decode("utf-8", errors="replace")
            del self._current_line[: line_end + 1]
            if self.report_received is not None:
                self.report_received(self, line)

    def close(self) -> None:
        try:
            self._handle.close()
        except (OSError, ValueError):
            pass
