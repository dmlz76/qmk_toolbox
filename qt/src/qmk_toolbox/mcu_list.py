from __future__ import annotations

from pathlib import Path

DEFAULT_MCU = "atmega32u4"


def load_mcu_list(path: str | Path) -> list[tuple[str, str]]:
    """Parse ``common/mcu-list.txt`` into ``(key, display name)`` pairs.

    The key is what the flasher tools expect (e.g. ``atmega32u4``).
    """
    mcus: list[tuple[str, str]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) == 2:
            mcus.append((parts[0], parts[1]))
    return mcus
