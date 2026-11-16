"""The keyboard drawn by the key tester, and how native key codes map onto it.

Keys are identified by physical position, not by the character they produce,
so the tester works the same whatever keyboard layout the OS is set to.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Key:
    id: str
    legend: str
    x: float  # position and size in key units (1 = one ordinary key)
    y: float
    width: float = 1.0
    height: float = 1.0


def _row(y: float, x: float, *entries) -> list[Key]:
    """Lay keys out left to right. Entries: ``(id, legend[, width])``, or a number for a gap."""
    keys = []
    for entry in entries:
        if isinstance(entry, (int, float)):
            x += entry
            continue
        key_id, legend, *rest = entry
        width = rest[0] if rest else 1.0
        keys.append(Key(key_id, legend, x, y, width))
        x += width
    return keys


def _letters(text: str) -> list[tuple[str, str]]:
    return [(c.lower(), c) for c in text]


NAV_X = 15.25
PAD_X = 18.5

KEYS: list[Key] = [
    *_row(0, 0, ("esc", "Esc"), 1.0,
          ("f1", "F1"), ("f2", "F2"), ("f3", "F3"), ("f4", "F4"), 0.5,
          ("f5", "F5"), ("f6", "F6"), ("f7", "F7"), ("f8", "F8"), 0.5,
          ("f9", "F9"), ("f10", "F10"), ("f11", "F11"), ("f12", "F12")),
    *_row(0, NAV_X, ("print_screen", "PrtSc"), ("scroll_lock", "ScrLk"), ("pause", "Pause")),

    *_row(1.25, 0, ("grave", "`"), *[(c, c) for c in "1234567890"], ("minus", "-"), ("equal", "="),
          ("backspace", "Backspace", 2.0)),
    *_row(1.25, NAV_X, ("insert", "Ins"), ("home", "Home"), ("page_up", "PgUp")),
    *_row(1.25, PAD_X, ("num_lock", "Num"), ("kp_slash", "/"), ("kp_asterisk", "*"), ("kp_minus", "-")),

    *_row(2.25, 0, ("tab", "Tab", 1.5), *_letters("QWERTYUIOP"), ("left_bracket", "["), ("right_bracket", "]"),
          ("backslash", "\\", 1.5)),
    *_row(2.25, NAV_X, ("delete", "Del"), ("end", "End"), ("page_down", "PgDn")),
    *_row(2.25, PAD_X, ("kp_7", "7"), ("kp_8", "8"), ("kp_9", "9")),
    Key("kp_plus", "+", PAD_X + 3, 2.25, 1.0, 2.0),

    *_row(3.25, 0, ("caps_lock", "Caps Lock", 1.75), *_letters("ASDFGHJKL"), ("semicolon", ";"), ("quote", "'"),
          ("enter", "Enter", 2.25)),
    *_row(3.25, PAD_X, ("kp_4", "4"), ("kp_5", "5"), ("kp_6", "6")),

    *_row(4.25, 0, ("left_shift", "Shift", 1.25), ("nubs", "\\"), *_letters("ZXCVBNM"), ("comma", ","),
          ("dot", "."), ("slash", "/"), ("right_shift", "Shift", 2.75)),
    *_row(4.25, NAV_X + 1, ("up", "↑")),
    *_row(4.25, PAD_X, ("kp_1", "1"), ("kp_2", "2"), ("kp_3", "3")),
    Key("kp_enter", "Ent", PAD_X + 3, 4.25, 1.0, 2.0),

    *_row(5.25, 0, ("left_ctrl", "Ctrl", 1.25), ("left_gui", "GUI", 1.25), ("left_alt", "Alt", 1.25),
          ("space", "", 6.25), ("right_alt", "Alt", 1.25), ("right_gui", "GUI", 1.25), ("menu", "Menu", 1.25),
          ("right_ctrl", "Ctrl", 1.25)),
    *_row(5.25, NAV_X, ("left", "←"), ("down", "↓"), ("right", "→")),
    *_row(5.25, PAD_X, ("kp_0", "0", 2.0), ("kp_dot", ".")),
]

WIDTH = max(key.x + key.width for key in KEYS)
HEIGHT = max(key.y + key.height for key in KEYS)

# Linux kernel input event codes (linux/input-event-codes.h). X11 and Wayland
# both report these plus 8 as the key's scan code.
_EVDEV = {
    1: "esc", 2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
    12: "minus", 13: "equal", 14: "backspace", 15: "tab",
    16: "q", 17: "w", 18: "e", 19: "r", 20: "t", 21: "y", 22: "u", 23: "i", 24: "o", 25: "p",
    26: "left_bracket", 27: "right_bracket", 28: "enter", 29: "left_ctrl",
    30: "a", 31: "s", 32: "d", 33: "f", 34: "g", 35: "h", 36: "j", 37: "k", 38: "l",
    39: "semicolon", 40: "quote", 41: "grave", 42: "left_shift", 43: "backslash",
    44: "z", 45: "x", 46: "c", 47: "v", 48: "b", 49: "n", 50: "m",
    51: "comma", 52: "dot", 53: "slash", 54: "right_shift", 55: "kp_asterisk", 56: "left_alt",
    57: "space", 58: "caps_lock",
    59: "f1", 60: "f2", 61: "f3", 62: "f4", 63: "f5", 64: "f6", 65: "f7", 66: "f8", 67: "f9", 68: "f10",
    69: "num_lock", 70: "scroll_lock",
    71: "kp_7", 72: "kp_8", 73: "kp_9", 74: "kp_minus", 75: "kp_4", 76: "kp_5", 77: "kp_6", 78: "kp_plus",
    79: "kp_1", 80: "kp_2", 81: "kp_3", 82: "kp_0", 83: "kp_dot",
    86: "nubs", 87: "f11", 88: "f12",
    96: "kp_enter", 97: "right_ctrl", 98: "kp_slash", 99: "print_screen", 100: "right_alt",
    102: "home", 103: "up", 104: "page_up", 105: "left", 106: "right", 107: "end", 108: "down",
    109: "page_down", 110: "insert", 111: "delete", 119: "pause",
    125: "left_gui", 126: "right_gui", 127: "menu",
}
LINUX_SCAN_CODES = {code + 8: key_id for code, key_id in _EVDEV.items()}

# macOS virtual key codes (kVK_* in Carbon's Events.h). A Mac keyboard has
# F13-F15, Help and Clear where a PC one has PrtSc/ScrLk/Pause, Insert and Num Lock.
MACOS_VIRTUAL_KEYS = {
    0x00: "a", 0x01: "s", 0x02: "d", 0x03: "f", 0x04: "h", 0x05: "g", 0x06: "z", 0x07: "x", 0x08: "c",
    0x09: "v", 0x0A: "nubs", 0x0B: "b", 0x0C: "q", 0x0D: "w", 0x0E: "e", 0x0F: "r", 0x10: "y", 0x11: "t",
    0x12: "1", 0x13: "2", 0x14: "3", 0x15: "4", 0x16: "6", 0x17: "5", 0x18: "equal", 0x19: "9", 0x1A: "7",
    0x1B: "minus", 0x1C: "8", 0x1D: "0", 0x1E: "right_bracket", 0x1F: "o", 0x20: "u", 0x21: "left_bracket",
    0x22: "i", 0x23: "p", 0x24: "enter", 0x25: "l", 0x26: "j", 0x27: "quote", 0x28: "k", 0x29: "semicolon",
    0x2A: "backslash", 0x2B: "comma", 0x2C: "slash", 0x2D: "n", 0x2E: "m", 0x2F: "dot", 0x30: "tab",
    0x31: "space", 0x32: "grave", 0x33: "backspace", 0x35: "esc",
    0x36: "right_gui", 0x37: "left_gui", 0x38: "left_shift", 0x39: "caps_lock", 0x3A: "left_alt",
    0x3B: "left_ctrl", 0x3C: "right_shift", 0x3D: "right_alt", 0x3E: "right_ctrl",
    0x41: "kp_dot", 0x43: "kp_asterisk", 0x45: "kp_plus", 0x47: "num_lock", 0x4B: "kp_slash",
    0x4C: "kp_enter", 0x4E: "kp_minus",
    0x52: "kp_0", 0x53: "kp_1", 0x54: "kp_2", 0x55: "kp_3", 0x56: "kp_4", 0x57: "kp_5", 0x58: "kp_6",
    0x59: "kp_7", 0x5B: "kp_8", 0x5C: "kp_9",
    0x60: "f5", 0x61: "f6", 0x62: "f7", 0x63: "f3", 0x64: "f8", 0x65: "f9", 0x67: "f11",
    0x69: "print_screen", 0x6B: "scroll_lock", 0x6D: "f10", 0x6E: "menu", 0x6F: "f12", 0x71: "pause",
    0x72: "insert", 0x73: "home", 0x74: "page_up", 0x75: "delete", 0x76: "f4", 0x77: "end", 0x78: "f2",
    0x79: "page_down", 0x7A: "f1", 0x7B: "left", 0x7C: "right", 0x7D: "down", 0x7E: "up",
}


def key_id_for(scan_code: int, virtual_key: int, platform: str = sys.platform) -> str | None:
    """The key at the physical position a native key event came from, if it is on the drawn keyboard."""
    if platform == "darwin":
        return MACOS_VIRTUAL_KEYS.get(virtual_key)
    if platform.startswith("linux"):
        return LINUX_SCAN_CODES.get(scan_code)
    return None
