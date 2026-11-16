#!/usr/bin/env python3
"""Print USB connect/disconnect events as the app would see them.

A development aid for checking device detection on real hardware before the
UI exists. Run from qt/:

    uv run python tools/watch_devices.py            # bootloaders only
    uv run python tools/watch_devices.py --all      # every USB device
    uv run python tools/watch_devices.py --reset atmega32u4

--reset asks each resettable bootloader to leave bootloader mode as soon as it
connects. It does not write anything to the device.
"""

from __future__ import annotations

import argparse
import time

from qmk_toolbox import environment
from qmk_toolbox.usb.usb_listener import UsbListener


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="also show devices that are not bootloaders")
    parser.add_argument("--reset", metavar="MCU", help="reset resettable bootloaders when they connect")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between polls (default: 1)")
    args = parser.parse_args()

    context = environment.create_flash_context()
    print(f"data directory: {environment.data_dir()}")
    for tool in ("avrdude", "bootloadHID", "dfu-programmer", "dfu-util", "hid_bootloader_cli",
                 "mdloader", "teensy_loader_cli", "wb32-dfu-updater_cli"):
        print(f"  {tool:22} {context.runner.find_tool(tool) or 'not found'}")
    print("watching for USB devices, Ctrl-C to stop\n")

    listener = UsbListener(context)
    to_reset = []

    def bootloader_connected(device):
        print(f"{device.name} device connected: {device}")
        if args.reset and device.resettable:
            to_reset.append(device)

    listener.bootloader_device_connected = bootloader_connected
    listener.bootloader_device_disconnected = lambda d: print(f"{d.name} device disconnected: {d}")
    listener.output_received = lambda d, message, type: print(f"  [{type.name}] {message}")
    if args.all:
        listener.usb_device_connected = lambda d: print(f"USB device connected: {d}")
        listener.usb_device_disconnected = lambda d: print(f"USB device disconnected: {d}")

    try:
        while True:
            listener.poll()
            while to_reset:
                to_reset.pop().reset(args.reset)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
