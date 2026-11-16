from enum import Enum, auto


class MessageType(Enum):
    BOOTLOADER = auto()
    COMMAND = auto()
    COMMAND_ERROR = auto()
    COMMAND_OUTPUT = auto()
    ERROR = auto()
    HID = auto()
    HID_OUTPUT = auto()
    INFO = auto()
    USB = auto()
