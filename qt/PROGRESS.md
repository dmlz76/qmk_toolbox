# Progress

Plan: [PLAN.md](PLAN.md). Update this file at the end of each working session.

## Status

| Step | State |
|---|---|
| 1. Core package | Done (2026-11-16) |
| 2. Device backends | Done (2026-11-16); checked on macOS with an Atmel DFU keyboard |
| 3. Main window | Done (2026-11-16); flash, Auto-Flash, drag-and-drop and settings verified on macOS |
| 4. HID console and key tester | Done (2026-11-16); both verified on macOS with a real keyboard |
| 5. Ubuntu work | Done (2026-11-16); `.deb` installed and verified on Ubuntu 26.04 with real keyboards |
| 6. CI and docs | Done (2026-11-16) except a first CI run on GitHub |

## Running the app

From `qt/`:

```sh
uv run qmk-toolbox            # optionally followed by a firmware file or a qmk:// link
```

## Building the Linux package

From `qt/`, on Ubuntu or Debian:

```sh
packaging/linux/build-deb.sh          # -> dist/qmk-toolbox_<version>-1_<arch>.deb (arm64: pass "arm64")
sudo apt install ./dist/qmk-toolbox_*.deb
```

The Maintainer field comes from `DEBFULLNAME`/`DEBEMAIL`, or else git config. Downloads are cached in `build/downloads/`.

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

Not verified: an actual firmware flash (first possible from the UI in step 3); anything on Linux (see step 5); serial-port matching against a real Caterina/SAM-BA device (in particular whether pyserial's `location` matches `UsbDevice.location` on each OS — if not, it falls back to the first VID/PID match); the LUFA MS mount lookup against a real device.

Known limitations:

- **LUFA MS mount lookup is a heuristic**: the first mounted volume containing both `FLASH.BIN` and `EEPROM.BIN`. It is not traced back to the USB device.
- **Install hints** (only seen when running from a checkout) name apt/Homebrew packages for avrdude, dfu-programmer, dfu-util and teensy_loader_cli; the apt names were verified on Ubuntu 26.04 in step 5, the Homebrew ones were not. The other four tools point to qmk_flashutils.

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

Also not verified: light theme and theme switching by eye; clicking through the menus and dialogs by hand (file dialog, About).

Deliberate differences from the macOS app:

- **`qmk:` downloads are restricted** to http/https links to .hex/.bin files, and an existing file of the same name in Downloads is replaced (the macOS app fails in that case).
- **Buttons are disabled while Auto-Flash is on.**
- **No "QMK Toolbox Help" menu item.**

Deferred from this step:

- Registering the app for .hex files and the `qmk:` URL scheme, and single-instance behaviour — both done in step 5. `.bin` files are not registered: their MIME type is `application/octet-stream`, and claiming that would offer the app for every unknown file.

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

Linux was verified in step 5.

Deliberate differences from the macOS app:

- **The key tester draws a PC-style keyboard** (PrtSc/ScrLk/Pause, Ins, Num Lock; modifiers labelled Ctrl/GUI/Alt) rather than a Mac one. On macOS F13–F15, Help and Clear light up the keys in those positions. fn, F16–F19 and keypad `=` have no key drawn and only update the labels.
- **Held keys are released when the window loses focus**, since their key-up events go elsewhere.

Possible improvement, raised 2026-11-16 and deferred: on macOS, label the key tester's modifiers Option and Command instead of Alt and GUI.

Known limitations:

- **On Linux the `hidraw` module is tried before `hid`.** With cython-hidapi the `hid` module uses libusb there, which detaches the keyboard from the kernel while the console is open (on Ubuntu 26.04 it also found no devices at all). Both the PyPI wheel and Ubuntu's `python3-hid` ship `hidraw`.
- **The key tester does nothing on Windows** (no scan-code table).

## Step 5 — Ubuntu (done)

Added:

- `udev.py` — whether udev has finished with a device, from its entry in `/run/udev/data`. A device shows up in sysfs (and so to libusb and pyserial) before udev has applied its rules, so a flasher started at once by Auto-Flash could be refused access. On Linux, `PyUsbBackend.scan` now leaves a device out until udev is done with it, and `find_serial_port` does the same for the tty.
- `environment.py` — `flashers_dir()` (`QMK_TOOLBOX_FLASHERS_DIR`, or `qmk_toolbox/flashers/` in the package), searched before `PATH`; `avrdude_conf()` passes the bundled avrdude its own config with `-C`; `access_problem()` checks on Linux whether the user can open a bootloader's USB node (or its serial port), and the main window logs an error when a bootloader connects if not, pointing to qmk_udev.
- `ui/single_instance.py` — one instance per user, as on Windows: a second launch connects to a `QLocalServer` socket in `$XDG_RUNTIME_DIR` (user-only), hands over its file or `qmk:` link and its `XDG_ACTIVATION_TOKEN`, and exits. The running window selects the file and raises itself; the token is what lets GNOME on Wayland bring it to the front.
- `firmware.local_path()` — `file://` URLs (as desktop environments pass files with `%u`) become paths.
- `usb_backend.py` — root hubs' names are read from sysfs `usbN` (they showed blank before).
- `app.py` — window icon from the icon theme (`qmk-toolbox`).
- `packaging/linux/` — `build-deb.sh` and the files it installs: launcher (`/usr/bin/qmk-toolbox`, runs `python3 -I` with `/usr/lib/qmk-toolbox` on the path), `.desktop` file (`.hex` files and `qmk:` links, `StartupNotify`, `SingleMainWindow`), a `text/x-ihex` MIME type for `*.hex` (shared-mime-info has none), hicolor icons from the macOS asset catalogue, `copyright`, `postinst` (byte-compiles; reloads udev and re-triggers hidraw devices) and `prerm`.

The package layout is `/usr/lib/qmk-toolbox/` = the unpacked wheel (so `importlib.metadata` reports the version) + `qmk_toolbox/data/` (from `common/`) + `qmk_toolbox/flashers/` (qmk_flashutils 20260711: avrdude 8.1, bootloadHID, dfu-programmer 1.1.0, dfu-util 0.11-dev, hid_bootloader_cli, mdloader 1.07, teensy_loader_cli, wb32-dfu-updater_cli 1.0.0, all statically linked); `/usr/lib/udev/qmk_id` and `/usr/lib/udev/rules.d/50-qmk.rules` (qmk_udev v0.1.23). Dependencies are all from the Ubuntu archive: python3-pyside6.qtwidgets/.qtnetwork 6.10.2, python3-usb 1.2.1, python3-serial 3.5, python3-hid 0.15.0, and `qt6-wayland | qt6-qpa-plugins`.

Findings on Ubuntu 26.04 (amd64, GNOME on Wayland, Python 3.14):

- Ubuntu packages avrdude 7.1, dfu-programmer 1.1.0, dfu-util 0.11 and teensy-loader-cli 2.2, and not bootloadHID, mdloader, hid_bootloader_cli or wb32-dfu-updater_cli. Moot for the package now that it bundles qmk_flashutils.
- QMK moved its udev rules out of qmk_firmware into qmk/qmk_udev (2026-04). The new rules no longer give the user every hidraw device: `qmk_id` reads each report descriptor and tags only QMK's console, raw HID and XAP endpoints. The rules also set `ID_MM_DEVICE_IGNORE` on Caterina and SAM-BA bootloaders, which is what keeps ModemManager (1.25.95, running by default) off their serial ports.
- An older `/etc/udev/rules.d/50-qmk.rules` (from an earlier `qmk setup`) overrides the package's file of the same name. It still works but grants every hidraw device; delete it to get the narrow rules. The development laptop still has one.

Verified on the development laptop (2026-11-16):

- 118 unit tests pass, both with the uv environment (PySide6 6.12, pyusb 1.3.1) and against Ubuntu's own packages (PySide6 6.10.2, pyusb 1.2.1), via a venv with system site packages.
- `apt install` of the `.deb` pulled 32 packages, all from the archive. The app appears in the GNOME app grid with its icon, runs natively on Wayland (`libqwayland`, GTK platform theme), reports version 0.3.4, and finds all eight bundled flashers and the bundled `avrdude.conf`. `.hex` files and `qmk:` links are associated with it.
- **Flash:** a wired mini-mighty-kbd (ATmega16U2, Atmel DFU 03EB:2FEF) was detected without a permission error (udev gave the user an ACL on the node), and flashed, validated and reset with the bundled dfu-programmer; the final reset returned at once.
- **HID console:** the mini-mighty-kbd-wireless (ATmega32U4, console firmware) was found through `hidraw` and its output shown line by line, while the keyboard kept typing.
- **Key tester:** every key of the wireless keyboard lit up in the right place under Wayland.
- **Single instance:** double-clicking a `.hex` in Files with the app open raised the running window; no second process.

Not verified:

- The arm64 package (not built).
- Serial bootloaders (Caterina, AVRISP, SAM-BA) and ModemManager on real hardware; LUFA MS mounting; any bootloader other than Atmel DFU on Linux.
- The `access_problem` error on real hardware (the rules were in place); only unit tests.
- Removing the package (`prerm`).
- X11 sessions.

Deliberate differences from the macOS app:

- **Single instance** as on Windows (macOS gets it from LaunchServices).
- **Bootloaders appear in the log only once udev has set them up**, a few milliseconds later than the kernel reports them.
- **An inaccessible bootloader is reported** on connect, with a pointer to the udev rules.

## Step 6 — CI and docs (done, not yet run on GitHub)

Added:

- `.github/workflows/build.yml` — a `build_linux` job, once for amd64 (`ubuntu-latest`) and once for arm64 (`ubuntu-24.04-arm`), each in an `ubuntu:26.04` container: installs Ubuntu's python3-pyside6 and the other dependencies from the archive, runs the tests with them (`python3 -m pytest`, not uv, so they run against what the package uses), builds the `.deb` for its own architecture, installs it with apt and starts it for 5 s on Qt's offscreen platform (it must still be running, with no traceback on stderr). The packages are uploaded as `qmk-toolbox-linux-<arch>` and attached to releases and the beta by the existing publish jobs, which now also wait for `build_linux`.
- Maintainer of CI-built packages: the repository variables `DEBFULLNAME`/`DEBEMAIL`, else `QMK <hello@qmk.fm>` (QMK's contact address, used in its code of conduct and workflows).
- `.github/labeler.yml` — a `linux` label for changes under `qt/`.
- `readme.md` — Ubuntu 26.04 in the requirements, the udev rules (and the old `/etc/udev/rules.d/50-qmk.rules`), download links for both packages, `apt install`, a pointer to `qt/`.
- `qt/README.md` — running from source, tests, building the package.
- `CLAUDE.md` — the CI job, where the bootloader parity changes go in `qt/`, the package file names in the readme's links as part of a version bump.
- `packaging/linux/copyright` — each flasher's licence, from its source: avrdude, dfu-programmer, dfu-util GPL-2+; bootloadHID GPL-2 or GPL-3; hid_bootloader_cli and teensy_loader_cli GPL-3 only; mdloader GPL-3+; wb32-dfu-updater_cli Apache-2.0; qmk_id GPL-2+ (it said "GPL-2+ and others" and "GPL" before).

Verified on the development laptop (Ubuntu 26.04):

- The 118 tests pass with the system's Python packages in a bare environment (`env -i`, no display), as the CI step runs them.
- The arm64 package builds from amd64 with `DEBFULLNAME=QMK DEBEMAIL=hello@qmk.fm`: aarch64 flashers and `qmk_id`, Maintainer `QMK <hello@qmk.fm>`.
- The smoke test's command against the installed package (offscreen, no display, empty runtime and config directories): still running after 5 s, no traceback.
- The workflow and labeler files parse, and the job has the expected steps and matrix. Not linted with actionlint.

Not verified:

- **The workflow has not run on GitHub.** It only runs on pushes to `master`, on releases and on pull requests, so the first run needs a pull request (e.g. `qt-port` → `master` on the fork). Untested in particular: the container on the ARM runner, `setup-uv` inside the container, the publish steps' `./qmk-toolbox-linux-*/*.deb` glob.
- The arm64 package with a real keyboard.
- The readme's download links (they work once a release with the packages exists).

Licences of the bundled flashers (raised in step 5, checked and decided here):

- The complete corresponding source of the flashers is qmk_flashutils at the commit in `flashutils_release_*` (7b9cff3) with its submodules (bootloadHID is vendored there as a tarball; libftdi and libserialport come from git:// servers outside GitHub), plus QMK's cross toolchain (`x86_64-qmk-linux-gnu-gcc`), whose C library is linked into the static binaries.
- The package only points to that repository. For the GPL-3 tools (teensy_loader_cli, hid_bootloader_cli, mdloader) GPL-3 §6(d) allows source on a third party's server, if the distributor makes sure it stays available. For the GPL-2+ tools (avrdude, dfu-programmer, dfu-util), GPL-2 §3 asks for the source to accompany the binaries, a written offer, or equivalent access "from the same place".
- The native macOS and Windows apps already bundle builds of the same GPL tools without shipping their source, so the Linux package does what QMK already does.
- **Decided (2026-11-16): do as the native apps do.** No source archive is attached to releases; `copyright` points to qmk_flashutils at the pinned commit. The more conservative option, if that is ever wanted, is to attach qmk_flashutils at that commit with its submodules to each release next to the packages.

## Background

- **Flashers.** First decided (2026-11-16) to use the system's, since the binaries in `macos/QMK Toolbox/Resources/` are x86_64-only and do not run on the arm64 development Mac without Rosetta. Revised the same day in step 5: the Linux package bundles qmk_flashutils, and runs from a checkout still use `PATH`. qmk_flashutils also has macOS arm64 builds, should the Mac ever need them. Homebrew on the Mac has `dfu-util` and `dfu-programmer` 1.1.0; the primary test devices use Atmel DFU, so `dfu-programmer` matters most.
- **`dfu-programmer reset` can hang on macOS 27.** After the chip leaves DFU the process often never returns, although the reset worked. The installed native QMK Toolbox on the development Mac is patched with a wrapper script that kills `reset`/`launch` after 5 s and reports success. Handled here in step 2 with a timeout. Homebrew's 1.1.0 build did not hang in two standalone resets, but did hang on the reset after a real flash (2026-11-16), where the timeout recovered as intended.
