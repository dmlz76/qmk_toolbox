# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

QMK Toolbox is a desktop GUI that detects keyboards in bootloader mode over USB and flashes firmware by shelling out to bundled third-party flasher CLIs (avrdude, dfu-util, dfu-programmer, etc.). It also has a HID console (`hid_listen`-compatible, usage page `0xFF31` / usage `0x0074`) and a key tester.

It is **two independent native apps that are kept at feature parity by hand**, not a cross-platform codebase:

- `macos/` — Swift 5 / AppKit (storyboard), Xcode project, deployment target macOS 12
- `windows/` — C# / WinForms, .NET 6 (`net6.0-windows10.0.19041.0`), single-file self-contained publish
- `common/` — data files shared by both apps (`avrdude.conf`, `mcu-list.txt`, `reset*.eep`), referenced by relative path from the Xcode project and as linked `EmbeddedResource`s in the `.csproj`

Almost any behavioural change (new bootloader, new VID/PID, changed flasher arguments, log text) must be made in both `macos/` and `windows/`. The two trees mirror each other file-for-file (e.g. `USB/Bootloader/CaterinaDevice.swift` ↔ `Usb/Bootloader/CaterinaDevice.cs`).

## Python/Qt port (in progress, `qt-port` branch)

`qt/` is a third implementation (Python + PySide6) aimed at Linux, also runnable on macOS. It is a self-contained project that mirrors the Swift app's structure and does not touch `macos/` or `windows/`. Before working on it, read `qt/PLAN.md` (goal, decisions, steps) and `qt/PROGRESS.md` (what is done, what has and has not been verified, notes for the next step), and update `PROGRESS.md` at the end of each session. From `qt/`: `uv run pytest` runs its tests, `uv run qmk-toolbox` runs the app.

## Build

There are no tests and no linter for the native apps. CI (`.github/workflows/build.yml`) only builds and packages.

macOS (from `macos/`):

```sh
xcodebuild CONFIGURATION_BUILD_DIR=build          # produces build/QMK Toolbox.app
packagesbuild -v "QMK Toolbox.pkgproj"            # installer; needs `brew install packages`
```

Windows (from `windows/`, only buildable on Windows):

```sh
dotnet publish -c Release -r win-x64 --self-contained true   # -> QMK Toolbox/bin/Release/win-x64/publish/qmk_toolbox.exe
iscc install_compiler.iss                                    # Inno Setup installer
```

CI fails the macOS build if the flasher binaries in `macos/QMK Toolbox/Resources/` are not mode `755` — preserve the executable bit when replacing them.

Pushes to `master` publish a rolling `beta` prerelease; publishing a GitHub release attaches the artifacts. macOS signing/notarization runs in the `sign_macos` job via `scripts/macos-signing.sh` (never on pull requests), using secrets from the `release-signing` environment.

## Architecture

Both apps share the same shape:

1. **USB listener** (`USBListener.swift` / `UsbListener.cs`) watches for device connect/disconnect (IOKit notifications on macOS, WMI `Win32_PnPEntity` event watchers on Windows). For each device, the listener's device-type switch maps VID/PID (and for Atmel devices the revision BCD `0x0936`, to distinguish QMK DFU/HID from stock Atmel/LUFA) to a `BootloaderType`, and `createDevice` / `CreateDevice` instantiates the matching `BootloaderDevice` subclass. Unrecognised devices stay plain `USBDevice`s and are only logged when "show all devices" is on.
2. **`BootloaderDevice` subclasses** (`USB/Bootloader/`) are thin: each sets `name`, `type`, `eepromFlashable`, `resettable` (and on Windows `PreferredDriver`) and overrides `flash` / `flashEEPROM` / `reset` to call `runProcess` with the right CLI and arguments. The base class runs the bundled binary with the resource directory as the working directory and streams stdout/stderr back as typed log messages (`MessageType`). Caterina and AVRISP also resolve a serial/COM port; LUFA Mass Storage copies a file to a mounted volume instead of running a CLI.
3. **Main window** (`MainViewController.swift` / `MainWindow.cs`) is the listener's delegate: it logs events to the coloured log view and implements flash/reset/clear-EEPROM by iterating over all currently connected bootloader devices. Auto-flash triggers `flashAll()` on bootloader connect.
4. **HID** (`HID/` / `Hid/`) is a separate listener for console devices feeding the HID console window.

Bundled flashers:

- macOS: prebuilt binaries and dylibs in `macos/QMK Toolbox/Resources/`, run directly from the app bundle.
- Windows: `.exe`/`.dll` files are `EmbeddedResource`s, extracted at startup to `%LOCALAPPDATA%\QMK\Toolbox` by `Helpers/EmbeddedResourceHelper.cs` and run from there. A new binary must be added in three places: `Resources/`, the `.csproj` `EmbeddedResource` list, and the `Resources` array in `EmbeddedResourceHelper.cs`.

### Adding a bootloader or device ID

Do each step on both platforms:

- add the case to `BootloaderType`
- add the VID/PID mapping in the listener's device-type switch, and the case in `createDevice`
- add the `BootloaderDevice` subclass (the Xcode project needs the new file in `project.pbxproj`)
- Windows only: if the device needs a WinUSB/libusb driver, add a line to `windows/QMK Toolbox/Resources/drivers.txt` (format documented in the file header; each entry needs a fresh GUID)
- update the supported-bootloader list in both `readme.md` and the startup log messages in the main window of each app

`common/mcu-list.txt` (`avrdude-id:Display Name` per line) populates the microcontroller dropdown on both platforms.

## Version bumps

The version string is duplicated; a bump touches all of these (see commit `22f0516`):

- `readme.md`
- `macos/QMK Toolbox/Info.plist`
- `macos/QMK Toolbox.pkgproj`
- `windows/QMK Toolbox/QMK Toolbox.csproj` (`AssemblyVersion`, `FileVersion`, `Version`)
- `windows/install_compiler.iss`
- `windows/QMK Toolbox/Properties/DataSources/WindowState.datasource`

## Conventions

- Windows sources are CRLF with a UTF-8 BOM; keep that when editing.
- `*.Designer.cs`, `.resx`, `Main.storyboard` and `.xib` files are designer-generated — edit with care and keep changes minimal.
