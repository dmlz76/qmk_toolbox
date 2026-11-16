# QMK Toolbox — cross-platform (Python + Qt) port: plan

Status is tracked in [PROGRESS.md](PROGRESS.md).

## Goal

A third implementation of QMK Toolbox, next to `macos/` (Swift/AppKit) and `windows/` (C#/WinForms), that:

- runs well on Ubuntu (target: 26.04) — this is the primary reason it exists
- also runs on macOS, so most development and testing can happen there
- keeps Windows possible later, but out of scope for now

## Decisions

- **Stack:** Python + PySide6 (Qt 6). Chosen over C#/Avalonia because cross-platform libraries absorb almost all the per-OS work (see below), and over C++/Qt because the app is small.
- **Location:** `qt/` at the repo root, a self-contained Python project (`src/` layout). `macos/` and `windows/` are not touched.
- **Structure mirrors the Swift app** (`usb/usb_device.py` ↔ `USB/USBDevice.swift`, one module per bootloader under `usb/bootloader/`), so parity changes are easy to apply across all three trees.
- **The core is Qt-free.** Bootloader classes, the VID/PID table and the process runner have no Qt or USB-library imports, so they are unit-testable without hardware. Qt is only used in the UI layer.
- **Flashers are not bundled.** The app uses the flasher CLIs installed on the system (found via `PATH`): apt packages on Ubuntu, Homebrew on macOS. When a tool is missing, the app says which one and how to install it. Tools the distribution does not package are handled at install time (step 5), not shipped inside the app. Downloading binaries on first launch is a fallback only if install-time handling turns out not to be workable, since it means running unsigned downloads and there are no known upstream prebuilt Linux binaries for those tools.
- **Shared data** (`mcu-list.txt`, `reset*.eep`, `avrdude.conf`) comes from `common/`, as for the other two apps.

## Libraries

| Need | Library | Per-OS code |
|---|---|---|
| UI | PySide6 | none |
| USB enumeration (VID/PID/revision) | `pyusb` over libusb, polled about once a second | none |
| HID console | `hidapi` | none |
| Serial port for Caterina / AVRISP / SAM-BA | `pyserial` `list_ports` | none |
| LUFA Mass Storage mount point | — | small per-OS function |
| Flasher binaries | — | none: system-installed tools found via `PATH`; per-OS install hints only |

## Steps

1. **Core package.** Message types, `UsbDevice`, bootloader types, VID/PID → bootloader mapping, one class per bootloader, process runner streaming output as typed log messages, MCU list loader. Unit tests.
2. **Device backends.** USB listener (pyusb, polling) emitting connect/disconnect events, serial-port lookup, mount-point lookup, flasher-binary and data-directory lookup. Test on macOS against a real keyboard.
3. **Main window.** Coloured log, firmware file picker with recent files, MCU picker, flash / reset / clear EEPROM / set handedness, auto-flash, "show all devices". Flashing runs off the UI thread.
4. **HID console and key tester.**
5. **Ubuntu work** (on the Linux laptop): udev rules for non-root access, ModemManager interference with serial bootloaders, flasher packages from apt plus building the ones Ubuntu does not ship, `.deb` packaging.
6. **CI and docs.** Build job in `.github/workflows/build.yml`, readme, `CLAUDE.md`.

## Open questions

- **avrdude.conf on Linux.** `common/avrdude.conf` matches the avrdude bundled with the macOS/Windows apps. A system avrdude from apt should use its own config, so the avrdude-based bootloaders only pass `-C` when a config path is supplied. Decide in step 2/5 which platforms supply one.
- **Which flashers Ubuntu 26.04 packages.** Believed available: avrdude, dfu-util, dfu-programmer, teensy-loader-cli. Believed missing: bootloadHID, mdloader, hid_bootloader_cli, wb32-dfu-updater_cli. Not yet verified.
- **Qt packages on Ubuntu 26.04.** Whether the archive's PySide6 is sufficient for a `.deb` with apt-only dependencies, or whether we need to bundle. Not yet verified.
- **macOS distribution.** Not planned; on macOS this is a development convenience. The native app stays the shipped one.
- **Windows.** Out of scope; libusb enumeration and driver handling there need separate investigation.
- **Upstreaming.** Undecided whether this goes to `qmk/qmk_toolbox` or stays in a fork.
