from enum import Enum, auto


class BootloaderType(Enum):
    APM32_DFU = auto()
    ATMEL_DFU = auto()
    ATMEL_SAMBA = auto()
    AVR_ISP = auto()
    BOOTLOADHID = auto()
    CATERINA = auto()
    GD32V_DFU = auto()
    HALFKAY = auto()
    KIIBOHD_DFU = auto()
    LUFA_HID = auto()
    LUFA_MS = auto()
    QMK_DFU = auto()
    QMK_HID = auto()
    STM32_DFU = auto()
    STM32DUINO = auto()
    USBASP = auto()
    USBTINYISP = auto()
    WB32_DFU = auto()
    NONE = auto()
