from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from ..mcu_list import DEFAULT_MCU


class MicrocontrollerSelector(QComboBox):
    """Shows the display names from mcu-list.txt; ``selected_key`` is what the flashers expect."""

    def __init__(self, mcus: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        for key, name in mcus:
            self.addItem(name, key)
        self.select_key(DEFAULT_MCU)

    def select_key(self, key: str) -> None:
        index = self.findData(key)
        if index >= 0:
            self.setCurrentIndex(index)

    def selected_key(self) -> str:
        return self.currentData() or ""
