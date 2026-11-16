# Progress

Plan: [PLAN.md](PLAN.md). Update this file at the end of each working session.

## Status

| Step | State |
|---|---|
| 1. Core package | Done (2026-11-16) |
| 2. Device backends | Done (2026-11-16); checked on macOS with an Atmel DFU keyboard |
| 3. Main window | Not started — next |
| 4. HID console and key tester | Not started |
| 5. Ubuntu work | Not started |
| 6. CI and docs | Not started |

## Running the tests

From `qt/`:

```sh
uv run pytest
```

`uv` creates `.venv/` and installs the dependencies (pyusb, pyserial, pytest) on first use. The tests need no hardware. pyusb needs libusb at run time (`brew install libusb` on macOS, already present on Ubuntu).

## Step 1 — core package (done)

Ported from the Swift app, under `src/qmk_toolbox/`:

- `message_type.py`, `mcu_list.py`
- `process_runner.py` — finds a flasher (bundled directories first, then `PATH`), runs it, and streams stdout/stderr line by line as typed messages. Blocking; meant to be called off the UI thread.
- `usb/usb_device.py`, `usb/device_factory.py` — the VID/PID table and `create_device`
- `usb/bootloader/` — `BootloaderDevice`, `FlashContext`, and one module per bootloader (18 classes)

Verified: unit tests pass on macOS, covering the VID/PID mapping, the exact command line of every bootloader, and the process runner against real subprocesses. One test parses `USBListener.swift` and fails if the VID/PID table drifts from the macOS app. The runner was also checked by hand against Homebrew's `dfu-util --version`.

Not verified: nothing has been run against real hardware, and nothing has been run on Linux.

Deliberate differences from the Swift app:

- **Serial port / mount point lookup is lazy.** Swift blocks in the constructor until the port appears; here the lookup is retried on each use and flashing reports "Serial port not found!" / "Mount point not found!" if it is still missing (as the Windows app does for COM ports).
- **avrdude `-C` is optional.** It is only passed when `FlashContext.avrdude_conf` is set, so a system avrdude can use its own config.
- **Command output is forwarded per line**, with a bare `\r` treated as a line break, so progress bars arrive as several lines rather than one chunk.
- **A missing flasher binary is reported** as "Could not find <tool>" instead of a generic launch error.

## Step 2 — device backends (done)

Added:

- `process_runner.py` — optional `timeout` on `run` (kills the process and raises `subprocess.TimeoutExpired`), and an `install_hint` shown when a flasher is missing.
- `usb/bootloader/atmel_dfu_device.py` — `dfu-programmer reset` is given 5 s, both as the last step of a flash and for the Reset button. If it does not return it is killed and a normal (non-error) message is logged. This replaces the wrapper-script workaround used with the native macOS app.
- `usb/usb_backend.py` — `PyUsbBackend`: enumerates with pyusb without opening devices; reads manufacturer/product strings once per new device (from sysfs on Linux, from the device elsewhere) and closes the device again.
- `usb/usb_listener.py` — `UsbListener.poll()` diffs the attached devices against the known ones and fires connect/disconnect callbacks. No thread or timer inside; the UI will call it from a timer.
- `usb/usb_device.py` — `bus`, `address`, `port_numbers`, and `location` (e.g. `1-1.4`).
- `environment.py` — data directory lookup (`QMK_TOOLBOX_DATA_DIR`, packaged `data/`, or the repo's `common/`), extra flasher directories (Homebrew's, on macOS), per-OS install hints, serial-port lookup via pyserial, LUFA MS mount-point lookup, and `create_flash_context()`.
- `tools/watch_devices.py` — prints the flashers found and connect/disconnect events; `--all` for non-bootloaders, `--reset MCU` to reset bootloaders as they connect.

Verified on macOS (arm64, macOS 27, Python 3.14 via uv): 63 unit tests pass. `watch_devices.py --all` listed the nine USB devices attached to the Mac with correct names and IDs, and found Homebrew's `dfu-programmer` and `dfu-util`.

Verified on hardware (2026-11-16, macOS): with `watch_devices.py --all`, a mini-mighty-kbd-wireless (04D8:FFF1, ATmega32U4) entering bootloader mode was reported as a USB disconnect followed by "Atmel DFU device connected: ATMEL ATm32U4DFU (03EB:2FF4:0000)", and leaving it as the reverse. Each event was reported exactly once.

With `watch_devices.py --reset atmega32u4`, the same keyboard was reset out of bootloader mode twice: each time the `dfu-programmer atmega32u4 reset` command was logged and the device disconnected. Homebrew's dfu-programmer 1.1.0 returned within the 5 s limit both times, so the timeout path has only been exercised by unit tests, not by a real hang. Two runs do not show the hang cannot happen with this build; the timeout stays as a guard.

Not verified: an actual firmware flash (first possible from the UI in step 3); anything on Linux; serial-port matching against a real Caterina/SAM-BA device (in particular whether pyserial's `location` matches `UsbDevice.location` on each OS — if not, it falls back to the first VID/PID match); the LUFA MS mount lookup against a real device.

Known limitations:

- **LUFA MS mount lookup is a heuristic**: the first mounted volume containing both `FLASH.BIN` and `EEPROM.BIN`. It is not traced back to the USB device.
- **Install hints** name apt/Homebrew packages for avrdude, dfu-programmer, dfu-util and teensy_loader_cli only; the package names are from memory and unverified. The other four tools get a generic message.
- **`FlashContext.avrdude_conf` is unused** now that flashers come from the system; kept until step 5 settles whether any platform needs it.

## Notes for step 3

- Call `UsbListener.poll()` from a `QTimer` on the UI thread; run flash/reset/EEPROM on a worker thread and marshal `output_received` back with a signal (it is called from reader threads).
- `poll()` raises `UsbBackendError` when libusb is missing; show it once rather than every second.
- Pass EEPROM files as `environment.data_file("reset.eep")` etc.
- Do not poll-and-flash re-entrantly: with auto-flash, a connect callback should queue the flash rather than run it inside `poll()`.

## Background

- **Flashers come from the system, not the repo** (decided 2026-11-16, see PLAN.md). The binaries in `macos/QMK Toolbox/Resources/` are x86_64-only and do not run on the arm64 development Mac without Rosetta anyway. Homebrew there has `dfu-util` and `dfu-programmer` 1.1.0; the other six tools are not installed. The primary test device uses Atmel DFU, so `dfu-programmer` is the one that matters first.
- **`dfu-programmer reset` can hang on macOS 27.** After the chip leaves DFU the process often never returns, although the reset worked. The installed native QMK Toolbox on the development Mac is patched with a wrapper script that kills `reset`/`launch` after 5 s and reports success. Handled here in step 2 with a timeout. Homebrew's 1.1.0 build did not hang in two resets on 2026-11-16.
