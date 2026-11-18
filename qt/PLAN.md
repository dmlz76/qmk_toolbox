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
- **Flashers.** The Linux package (and the macOS app, step 7) bundles QMK's own flasher builds ([qmk_flashutils](https://github.com/qmk/qmk_flashutils): all eight tools, statically linked, for x86_64 and arm64) with their `avrdude.conf`, as the native apps bundle theirs. The release is pinned and checked against SHA-256 sums when the package is built; nothing is downloaded at run time. Run from a checkout, the app uses the flashers on `PATH` (apt, Homebrew) and says how to install a missing one. As with the native apps, the flashers' source is not shipped with the package; its `copyright` file points to qmk_flashutils at the pinned commit (decided 2026-11-16, see PROGRESS.md, step 6). Changed 2026-11-16: the first version of this plan used system flashers only, on the assumption that there were no upstream prebuilt Linux binaries; qmk_flashutils turned out to be exactly that.
- **udev rules** are QMK's own ([qmk_udev](https://github.com/qmk/qmk_udev)), installed unchanged by the package with their `qmk_id` helper, which grants access only to QMK's HID endpoints rather than to every hidraw device.
- **Shared data** (`mcu-list.txt`, `reset*.eep`, `avrdude.conf`) comes from `common/`, as for the other two apps.

## Libraries

| Need | Library | Per-OS code |
|---|---|---|
| UI | PySide6 | none |
| USB enumeration (VID/PID/revision) | `pyusb` over libusb, polled about once a second | none |
| HID console | `hidapi` | none |
| Serial port for Caterina / AVRISP / SAM-BA | `pyserial` `list_ports` | none |
| LUFA Mass Storage mount point | — | small per-OS function |
| Flasher binaries | qmk_flashutils, bundled in the package | none; from a checkout, tools on `PATH` with per-OS install hints |

## Steps

1. **Core package.** Message types, `UsbDevice`, bootloader types, VID/PID → bootloader mapping, one class per bootloader, process runner streaming output as typed log messages, MCU list loader. Unit tests.
2. **Device backends.** USB listener (pyusb, polling) emitting connect/disconnect events, serial-port lookup, mount-point lookup, flasher-binary and data-directory lookup. Test on macOS against a real keyboard.
3. **Main window.** Coloured log, firmware file picker with recent files, MCU picker, flash / reset / clear EEPROM / set handedness, auto-flash, "show all devices". Flashing runs off the UI thread.
4. **HID console and key tester.**
5. **Ubuntu work** (on the Linux laptop): udev rules for non-root access, ModemManager interference with serial bootloaders, flashers, `.deb` packaging, desktop integration.
6. **CI and docs.** Build job in `.github/workflows/build.yml`, readme, `CLAUDE.md`.
7. **macOS app** (added 2026-11-17). An app bundle in a `.dmg`, built locally with PyInstaller: Python, Qt and qmk_flashutils' macOS flashers bundled, named "QMK Toolbox (Qt)" with its own bundle ID so that it installs next to the native app. Signed ad hoc, for the Mac that builds it; not distributed. Earlier this plan said macOS distribution was not planned; changed on request, so the port can replace the native app on the development Mac too.

## Open questions

- **arm64.** The package builds, and CI installs and starts it on an ARM runner, but it has not been used with a keyboard.
- **Windows.** Out of scope; libusb enumeration and driver handling there need separate investigation.
- **Upstreaming.** Undecided whether this goes to `qmk/qmk_toolbox` or stays in a fork.
