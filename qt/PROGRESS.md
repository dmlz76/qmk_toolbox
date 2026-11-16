# Progress

Plan: [PLAN.md](PLAN.md). Update this file at the end of each working session.

## Status

| Step | State |
|---|---|
| 1. Core package | Done (2026-11-16) |
| 2. Device backends | Done (2026-11-16); checked on macOS with an Atmel DFU keyboard |
| 3. Main window | Done (2026-11-16); flash, Auto-Flash, drag-and-drop and settings verified on macOS |
| 4. HID console and key tester | Done (2026-11-16); both verified on macOS with a real keyboard |
| 5. Ubuntu work | Not started — next |
| 6. CI and docs | Not started |

## Running the app

From `qt/`:

```sh
uv run qmk-toolbox            # optionally followed by a firmware file or a qmk:// link
```

## Running the tests

From `qt/`:

```sh
uv run pytest
```

`uv` creates `.venv/` and installs the dependencies (PySide6-Essentials, hidapi, pyusb, pyserial, pytest) on first use. The tests need no hardware and no display (the UI tests use Qt's offscreen platform). pyusb needs libusb at run time (`brew install libusb` on macOS, already present on Ubuntu).

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

## Step 3 — main window (done)

Added:

- `ui/main_window.py` — the window: "Local file" row (editable recent-files box, Open, MCU picker), coloured log, Auto-Flash checkbox, Exit DFU / Clear EEPROM / Flash buttons, and File / Tools / Help menus mirroring the macOS app (shortcuts Ctrl+O, Ctrl+Shift+F/E/X).
- `ui/log_text_view.py` — log colours and prefixes copied from the macOS app, light and dark; the log is re-coloured if the system theme changes.
- `ui/microcontroller_selector.py`, `app.py`, `__main__.py`, and a `qmk-toolbox` entry point.
- `firmware.py` — firmware file check, `qmk:` link unwrapping, download to the Downloads folder.

Behaviour:

- Devices are polled every 500 ms from a timer on the UI thread.
- Flash / reset / EEPROM run on a worker thread, one operation at a time; the buttons are disabled meanwhile and the window refuses to close until the operation ends.
- With Auto-Flash on, a bootloader connecting starts a flash; one that connects during a flash is flashed afterwards. The buttons are disabled while Auto-Flash is on.
- Remembered between runs (QSettings, organisation "QMK"): MCU, Show All Devices, recent files (10), window geometry. Auto-Flash is not remembered, as in the macOS app.
- A firmware file can be chosen with Open, dropped on the window, picked from the recent list, or passed on the command line.

Verified on macOS: 85 unit tests pass, including headless UI tests that drive the window with a fake USB backend and fake flasher (button states, flash / reset / EEPROM command lines, locking during a flash, auto-flash, settings round trip, qmk link handling). The real window was launched once and a screenshot checked: layout and dark-theme colours are correct.

Verified on hardware (2026-11-16, macOS): a real flash from the UI. A mini-mighty-mouse (ATmega16U2, Atmel DFU 03EB:2FEF) was detected, erased, flashed and validated with Homebrew's dfu-programmer, with all output shown in the log. The final `dfu-programmer reset` hung after the device had already left DFU; the 5 s timeout killed it, logged "Reset sent, but dfu-programmer did not return within 5 s; stopped it." and the operation ended with "Flash complete". So the hang does occur with Homebrew's 1.1.0 build, and the timeout handles it.

Auto-Flash was also verified on the same device: with the box ticked, entering bootloader mode started the flash by itself, and it completed. That time `dfu-programmer reset` returned normally, so the hang is intermittent, as expected.

Drag and drop of a firmware file onto the window worked, and after relaunching the app the file and MCU were remembered.

The Exit DFU button was checked by hand as well.

Also not verified: light theme and theme switching by eye; anything on Linux; clicking through the menus and dialogs by hand (file dialog, About).

Deliberate differences from the macOS app:

- **`qmk:` downloads are restricted** to http/https links to .hex/.bin files, and an existing file of the same name in Downloads is replaced (the macOS app fails in that case).
- **Buttons are disabled while Auto-Flash is on.**
- **No "QMK Toolbox Help" menu item.**

Not done yet, and where it belongs:

- Registering the app for .hex/.bin files and the `qmk:` URL scheme — packaging, step 5 (`.desktop` file).
- Single-instance behaviour (the Windows app forwards a second launch to the running one) — not planned yet; decide in step 5.

## Step 4 — HID console and key tester (done)

Added:

- `hid/hid_device.py`, `hid/hid_backend.py`, `hid/hid_listener.py` — console (usage page `0xFF31`, usage `0x0074`) and raw HID (`0xFF60` / `0x0061`) devices via hidapi. Console devices are opened non-blocking; raw devices are only reported. Like the USB listener there are no threads: `poll()` finds devices, `read()` drains pending reports and assembles them into lines.
- `ui/hid_console_window.py` — device picker with "(All connected devices)", coloured log, Clear. Listens only while the window is open (polls every second, reads every 20 ms).
- `ui/key_layout.py`, `ui/key_tester_window.py` — a full-size ANSI keyboard with the extra ISO key, drawn in one widget. Keys light yellow while held and stay green once pressed. Keys are identified by physical position: scan codes on Linux (evdev code + 8), virtual key codes on macOS. The window takes every key for itself (Tab, Esc, shortcuts) and shows the native codes of the last key.
- Tools menu: Key Tester and HID Console.

Verified on macOS: 103 unit tests pass (console line assembly including split UTF-8, two keyboards, a device that stops answering or cannot be opened, key lookup tables, key tester state and painting). Both windows were launched and checked by screenshot. hidapi enumerated the Mac's 37 HID interfaces in about 4 ms and correctly found no console devices.

Verified on hardware (2026-11-16, macOS):

- **Key tester:** every key on the mini-mighty-kbd-wireless was detected at the correct position, modifiers included.
- **HID console:** console-enabled firmware was flashed to the keyboard with this app, and the HID Console window then showed "HID console connected: Dimitrix LLC mini-mighty-kbd-wireless (04D8:FFF1:0100)" followed by the keyboard's live output (`keyboard_report: ...` lines), one line per message.

Not verified: two console devices at once and raw HID devices on real hardware (unit tests only).

Also not verified: anything on Linux — the evdev scan-code table, and the `hidraw` module preference (see below).

Deliberate differences from the macOS app:

- **The key tester draws a PC-style keyboard** (PrtSc/ScrLk/Pause, Ins, Num Lock; modifiers labelled Ctrl/GUI/Alt) rather than a Mac one. On macOS F13–F15, Help and Clear light up the keys in those positions. fn, F16–F19 and keypad `=` have no key drawn and only update the labels.
- **Held keys are released when the window loses focus**, since their key-up events go elsewhere.

Possible improvement, raised 2026-11-16 and deferred: on macOS, label the key tester's modifiers Option and Command instead of Alt and GUI.

Known limitations:

- **On Linux the `hidraw` module is tried before `hid`.** With cython-hidapi the `hid` module uses libusb there, which detaches the keyboard from the kernel while the console is open. Whether Ubuntu's `python3-hid` package ships `hidraw` is unverified; check in step 5.
- **Reading a console on Linux needs permission on `/dev/hidraw*`** — part of the udev rules in step 5.
- **The key tester does nothing on Windows** (no scan-code table).

## Notes for step 5

- udev rules: bootloader USB devices (for the flashers) and hidraw access for console devices. QMK ships `50-qmk.rules`; start from that.
- Check on Ubuntu 26.04: apt names for the Python modules (PySide6, pyusb, pyserial, hidapi) and for the flashers; that `hidraw` imports; Wayland behaviour of the key tester.
- `.desktop` file: MIME types for .hex/.bin and the `x-scheme-handler/qmk` URL scheme.
- Decide on single-instance behaviour.

## Background

- **Flashers come from the system, not the repo** (decided 2026-11-16, see PLAN.md). The binaries in `macos/QMK Toolbox/Resources/` are x86_64-only and do not run on the arm64 development Mac without Rosetta anyway. Homebrew there has `dfu-util` and `dfu-programmer` 1.1.0; the other six tools are not installed. The primary test device uses Atmel DFU, so `dfu-programmer` is the one that matters first.
- **`dfu-programmer reset` can hang on macOS 27.** After the chip leaves DFU the process often never returns, although the reset worked. The installed native QMK Toolbox on the development Mac is patched with a wrapper script that kills `reset`/`launch` after 5 s and reports success. Handled here in step 2 with a timeout. Homebrew's 1.1.0 build did not hang in two standalone resets, but did hang on the reset after a real flash (2026-11-16), where the timeout recovered as intended.
