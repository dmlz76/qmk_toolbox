from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UsbDevice:
    vendor_id: int
    product_id: int
    revision_bcd: int
    manufacturer: str | None = None
    product: str | None = None
    # Where the device is attached; (bus, address) identifies it while connected.
    bus: int = 0
    address: int = 0
    port_numbers: tuple[int, ...] = ()

    @property
    def location(self) -> str:
        """Bus and port path, e.g. ``1-1.4`` (the form sysfs and pyserial use)."""
        return f"{self.bus}-{'.'.join(str(port) for port in self.port_numbers)}"

    def __str__(self) -> str:
        return "%s %s (%04X:%04X:%04X)" % (
            self.manufacturer or "",
            self.product or "",
            self.vendor_id,
            self.product_id,
            self.revision_bcd,
        )
