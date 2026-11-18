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
| 6. CI and docs | Done (2026-11-16); CI passed on GitHub for amd64 and arm64 |
| 7. macOS app | Done (2026-11-17); installed from the `.dmg`, flash, HID console and key tester verified on macOS |
| 8. Windows installer | Done (2026-11-18); installed on Windows 11 and briefly tried; flash, HID console and key tester verified from a checkout |

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

## Building the macOS app

From `qt/`, on a Mac:

```sh
packaging/macos/build-app.sh          # -> dist/QMK-Toolbox-Qt-<version>-<arch>.dmg, for this Mac's architecture
```

Open the `.dmg` and drag "QMK Toolbox (Qt)" into Applications. Needs only uv; downloads are cached in `build/downloads/`.

## Building the Windows installer

From `qt/`, on Windows, with uv and Inno Setup 6 (`winget install JRSoftware.InnoSetup`):

```sh
uv run --no-project --python 3.14 packaging/windows/build-installer.py   # -> dist/QMK-Toolbox-Qt-<version>-x64-setup.exe
```

Run the installer (it asks for administrator rights). Downloads are cached in `build/downloads/`.

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
- `ui/key_layout.py`, `ui/key_tester_window.py` — a full-size ANSI keyboard with the extra ISO key, drawn in one widget. Keys light yellow while held and stay green once pressed. Keys are identified by physical position: scan codes on Linux (evdev code + 8), virtual key codes on macOS, scan codes on Windows (set 1, added 2026-11-18, see "Windows trial"). The window takes every key for itself (Tab, Esc, shortcuts) and shows the native codes of the last key.
- Tools menu: Key Tester and HID Console.

Verified on macOS: 103 unit tests pass (console line assembly including split UTF-8, two keyboards, a device that stops answering or cannot be opened, key lookup tables, key tester state and painting). Both windows were launched and checked by screenshot. hidapi enumerated the Mac's 37 HID interfaces in about 4 ms and correctly found no console devices.

Verified on hardware (2026-11-16, macOS):

- **Key tester:** every key on the mini-mighty-kbd-wireless was detected at the correct position, modifiers included.
- **HID console:** console-enabled firmware was flashed to the keyboard with this app, and the HID Console window then showed "HID console connected: Dimitrix LLC mini-mighty-kbd-wireless (04D8:FFF1:0100)" followed by the keyboard's live output (`keyboard_report: ...` lines), one line per message.

Not verified: two console devices at once and raw HID devices on real hardware (unit tests only). Later, on Windows (2026-11-18), a raw HID device (a wireless dongle) was detected and reported on real hardware; see "Windows trial".

Linux was verified in step 5.

Deliberate differences from the macOS app:

- **The key tester draws a PC-style keyboard** (PrtSc/ScrLk/Pause, Ins, Num Lock; modifiers labelled Ctrl/GUI/Alt) rather than a Mac one. On macOS F13–F15, Help and Clear light up the keys in those positions. fn, F16–F19 and keypad `=` have no key drawn and only update the labels.
- **Held keys are released when the window loses focus**, since their key-up events go elsewhere.

Possible improvement, raised 2026-11-16 and deferred: on macOS, label the key tester's modifiers Option and Command instead of Alt and GUI.

Known limitations:

- **On Linux the `hidraw` module is tried before `hid`.** With cython-hidapi the `hid` module uses libusb there, which detaches the keyboard from the kernel while the console is open (on Ubuntu 26.04 it also found no devices at all). Both the PyPI wheel and Ubuntu's `python3-hid` ship `hidraw`.
- **The key tester did nothing on Windows** (no scan-code table). Added 2026-11-18; see "Windows trial".

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

## Step 6 — CI and docs (done)

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

Verified on GitHub (2026-11-16): the workflow only runs on pushes to `master`, on releases and on pull requests, so it was run through a draft pull request `qt-port` → `master` on the fork (dmlz76/qmk_toolbox#1, closed afterwards; run 44000475389). Actions had first to be enabled for the fork in its Actions tab. Every job passed: both Linux jobs (about a minute each) installed PySide6 6.10.2 from the archive, passed all 118 tests, built their package, installed it with apt and kept the app running for 5 s (stderr only had Qt's "XDG_RUNTIME_DIR not set" and "propagateSizeHints" notes), and uploaded `qmk-toolbox-linux-amd64` and `qmk-toolbox-linux-arm64`. The Windows and macOS builds passed too; signing and publishing were skipped, as on every pull request. GitHub noted that `ubuntu-latest` is moving to Ubuntu 26; the job is unaffected, since it runs in its own container.

Not verified:

- The publish steps' `./qmk-toolbox-linux-*/*.deb` glob (publishing only runs on `master` pushes and releases).
- The arm64 package with a real keyboard.
- The readme's download links (they work once a release with the packages exists).

Licences of the bundled flashers (raised in step 5, checked and decided here):

- The complete corresponding source of the flashers is qmk_flashutils at the commit in `flashutils_release_*` (7b9cff3) with its submodules (bootloadHID is vendored there as a tarball; libftdi and libserialport come from git:// servers outside GitHub), plus QMK's cross toolchain (`x86_64-qmk-linux-gnu-gcc`), whose C library is linked into the static binaries.
- The package only points to that repository. For the GPL-3 tools (teensy_loader_cli, hid_bootloader_cli, mdloader) GPL-3 §6(d) allows source on a third party's server, if the distributor makes sure it stays available. For the GPL-2+ tools (avrdude, dfu-programmer, dfu-util), GPL-2 §3 asks for the source to accompany the binaries, a written offer, or equivalent access "from the same place".
- The native macOS and Windows apps already bundle builds of the same GPL tools without shipping their source, so the Linux package does what QMK already does.
- **Decided (2026-11-16): do as the native apps do.** No source archive is attached to releases; `copyright` points to qmk_flashutils at the pinned commit. The more conservative option, if that is ever wanted, is to attach qmk_flashutils at that commit with its submodules to each release next to the packages.

## Step 7 — macOS app (done)

Added 2026-11-17, reversing the plan's earlier "macOS distribution: not planned". On a Mac the equivalent of the Linux package's App Center entry is an app bundle in /Applications (Launchpad, Spotlight, Dock). The Mac App Store is not an option: its sandbox does not allow the USB access and bundled flashers.

- `packaging/macos/build-app.sh` — builds `QMK Toolbox (Qt).app` with PyInstaller and wraps it in a `.dmg` with an Applications link. Python 3.14, Qt and the other dependencies are bundled (macOS has no system PySide6 to depend on, unlike Ubuntu), at the versions pinned with hashes in `packaging/macos/requirements.txt` (regenerate from `requirements.in`, command in that file). The flashers are qmk_flashutils 20260711 for the Mac's architecture, checked against `packaging/macos/SHA256SUMS`, whose values match the SHA-256 digests GitHub lists for the release assets. The icon is made from the native app's asset catalogue.
- `packaging/macos/qmk-toolbox.spec` — bundle ID `fm.qmk.toolbox.qt` and name "QMK Toolbox (Qt)", so it installs next to the native app (`fm.qmk.toolbox`) without replacing it. Registers `.hex`/`.bin` files with rank "Alternate" (the native app stays the default while it is installed) and the `qmk:` URL scheme; imports the `fm.qmk.hex` type the native app exports, so .hex files stay recognised after that app is removed.
- `ui/file_open_handler.py` — files opened from Finder or dropped on the Dock icon, and `qmk:` links from a browser, reach a Mac app as Qt FileOpen events rather than arguments; they are now passed to the main window (kept until it exists).
- `firmware.unwrap_qmk_url` — repairs links that went through Qt: it turns `qmk://https://host/...` into `qmk://https//host/...` (reads "https:" as a host with an empty port).
- `tests/test_single_instance.py` — the socket path is now under `/tmp`: under pytest's temporary directory it was longer than macOS allows (104 bytes), so three tests failed on macOS (they passed on Linux).

Verified on the development Mac (arm64, macOS 27.2): 120 tests pass. The build takes about 20 s; the app is 90 MB, the `.dmg` 38 MB. In the bundle: all eight flashers are native arm64 and run (avrdude 8.1, dfu-programmer 1.1.0, dfu-util 0.11-dev, mdloader 1.07, wb32-dfu-updater_cli 1.0.0; the other three answered), hidapi and the app's package metadata are present, and no file links to Homebrew. Started headless, the app stayed up and loaded libusb from inside the bundle. `codesign --verify --deep --strict` passes on the ad-hoc signature.

Verified on hardware (2026-11-17, macOS 27.2, arm64): installed from the `.dmg` into Applications next to the native app, and started normally. The log's first line read "QMK Toolbox 0.3.4", so the package metadata is found. The mini-mighty-kbd-wireless (Atmel DFU, ATmega32U4) was flashed with console-enabled firmware using qmk_flashutils' dfu-programmer 1.1.0: erase, program, validate and reset all succeeded, and that time the reset returned by itself (the hang is intermittent). The HID Console window then showed the keyboard's output, so hidapi works from inside the bundle, and the Key Tester worked.

Opening a `.hex` from Finder was verified too. While the native app is installed it stays the default, as intended by the "Alternate" rank, so a double click first opened the native app. After choosing QMK Toolbox (Qt) in the file's Get Info > Open with, a double click selected the file in the Qt app, both when it was already running (in that instance) and when it was not (starting it).

Not verified: dropping a file on the Dock icon (same FileOpen path as Finder).

Also not verified: a `qmk:` link (which app macOS sends it to while both are installed is up to macOS); serial bootloaders; x86_64 Macs; macOS versions other than 27.

Known limitations:

- **Signed ad hoc only.** Fine on the Mac that built it. A copy downloaded from elsewhere (e.g. a CI artifact) would be blocked by Gatekeeper until approved in System Settings; distributing it properly needs a Developer ID signature and notarization. qmk_flashutils' binaries are built against the macOS 10.6 SDK, which PyInstaller warns will cause trouble with the hardened runtime that notarization requires.
- **Built for one architecture**, the building Mac's; no universal build.
- **libusb comes from the build Mac's Homebrew**, collected by PyInstaller's pyusb hook (`brew install libusb` is needed to build). It is LGPL-2.1, linked dynamically. The build script fails if libusb, hidapi, the flashers or the data files are missing from the app, or if anything in it links to a library outside the app and macOS (checked against Homebrew's own `dfu-util`, which it flags).
- **Not built in CI.**
- The key tester still labels the Mac's Option and Command keys Alt and GUI (deferred in step 4).

## Windows trial (2026-11-17, not a planned step)

A first run on a Windows PC (Windows 11 Home 10.0.26200, x86_64), from a checkout. Windows is still out of scope in PLAN.md; this checked how far the port gets there.

Setup:

- **Smart App Control is on** on that PC, and blocks uv's own Python downloads (python-build-standalone builds are unsigned): querying them fails with exit status `0xc0e90002`. Python 3.14.10 from python.org (signed, `winget install Python.Python.3.14 --scope user`) runs, and `.venv` was created with it (`uv run --python 3.14`). uv's blocked download was uninstalled afterwards, so uv only finds the python.org one.
- **libusb and flashers** come from the native Windows app's `windows/QMK Toolbox/Resources/` (`libusb-1.0.dll`, dfu-programmer 1.1.0, dfu-util 0.11, avrdude, ...); Smart App Control lets them run. The app does not look there by itself yet, so for now (CMD, from `qt/`):

  ```bat
  set "RES=C:\path\to\qmk_toolbox\windows\QMK Toolbox\Resources"
  set "PATH=%RES%;%PATH%"
  set "QMK_TOOLBOX_FLASHERS_DIR=%RES%"
  uv run qmk-toolbox
  ```

  Without the `PATH` entry the window opens but logs "Cannot detect USB devices: libusb was not found". (No longer needed since step 8: the app finds that folder itself, and plain `uv run qmk-toolbox` works.)
- **Driver.** dfu-programmer needs a WinUSB (or libusb) driver bound to the bootloader. The PC had none at first; before the flash, 14 libwdi-generated WinUSB driver packages were installed within 21 s (`oem13.inf`–`oem29.inf`, 2026-11-17 23:10; 03EB:2FEF uses `oem23.inf`), which matches the native app's `qmk_driver_installer.exe --all --force drivers.txt` (from `Resources/`, run as administrator). The port can run that installer itself since step 8.

Fixed (all platforms' code, found on Windows):

- `firmware.local_path` used the URL's path as is, so `file:///C:/Users/...` became `/C:/Users/...` and later `C:\C:\Users\...`. Now `url2pathname`.
- `ProcessRunner.find_tool` and `environment.avrdude_conf` looked for `<dir>/avrdude`; on Windows the file is `avrdude.exe`. Both now use `shutil.which(tool, path=dir)`, which adds Windows' extensions and checks the executable bit elsewhere.
- `environment.find_mount_point` also looks at drive letters on Windows (`mount_volumes()`); `mount_roots()` is empty there.
- `ui/single_instance.py`: on Windows (named pipes) the running instance accepted the connection, but whatever it had not read when the second launch disconnected was lost, so a hand-over could arrive empty. The message is now a line ending in `\n`; the running instance reads until the newline and then closes the connection, and the second launch waits for that close (up to 1 s) instead of disconnecting first. The pipe name on Windows is `qmk-toolbox-<user>`: the runtime-directory path used elsewhere contains a backslash, which Windows does not allow in pipe names.
- **Key tester on Windows** (added 2026-11-18; it did nothing there before): `key_layout.WINDOWS_SCAN_CODES`, keyed by Qt's `nativeScanCode()`. That is the key's scan code set 1 make code, the same numbers as the Linux kernel's codes for the main block, with `0xE000` added for extended (E0-prefixed) keys. The prefix was checked with keys injected through `SendInput`: right Ctrl came through as `E01D`, Up as `E048`; it is not the `0x100` of the raw keyboard message. Pause is `45` and Num Lock `E045`, from Windows' documentation (Pause later confirmed on hardware); injected events cannot confirm those two (they came through as `0` and `E000`). Also mapped: `54` (Alt+PrtSc) to PrtSc and `E046` (Ctrl+Pause) to Pause.
- Tests: fake flashers are `.cmd` files on Windows (no shebang lines); the single-instance tests start the second launch as a real process (with both ends in one process, Windows' pipes still lost messages now and then, about 1 in 30), and the stale-socket test is skipped on Windows (a named pipe goes away with its process); path assertions no longer assume `/`.

Verified on Windows:

- 119 tests pass, 2 skipped (the POSIX `local_path` test and the stale-socket test), in 10 consecutive full runs.
- Single-instance hand-over between two real processes: 30 of 30 arrived, each in about 10 ms.
- The window starts with the full startup log, light theme, no errors.
- **Flash (hardware):** a mini-mighty-kbd (ATmega16U2, Atmel DFU 03EB:2FEF) was detected as "ATMEL ATmega16u2 DFU" (so libusb could read its strings through WinUSB), erased, flashed, validated and reset with the native app's dfu-programmer 1.1.0; the reset returned by itself, and the disconnect was logged.
- **HID console (hardware, 2026-11-18):** the HID Console window reported "HID console connected: Dimitrix LLC mini-mighty-kbd-wireless (04D8:FFF1:0100)" and showed its `keyboard_report:` lines live, one per report (typing q w e r t y gave press and release lines for each). It also reported "Raw HID device connected: dimitrix llc mini-mighty-dongle (04D8:FFF2:0100)", the first raw HID device seen on real hardware on any platform (step 4 had only unit tests for it). No driver was needed for either: Windows' own HID driver serves them.
- **Key tester (hardware, 2026-11-18):** every key of the mini-mighty-kbd lit up in the right place, Pause included, so Windows' documented code for it (`45`) is right.

Not verified:

- **These changes on macOS and Linux**: the tests have not been rerun there since. The single-instance protocol change in particular affects both.
- On Windows: opening a `.hex` with the app running (only the tests and a script); serial bootloaders and COM-port matching; LUFA MS on a drive letter; any bootloader other than Atmel DFU; the key tester's Num Lock and Print Screen on a real keyboard (Windows 11 opens the Snipping Tool on PrtSc, so the app may only see the key's release, which does not mark it tested).

The gaps this left on Windows (libusb and flashers only found through environment variables, no driver installation, no packaging) were closed in step 8; what is still missing is listed there.

## Step 8 — Windows installer (done)

Added 2026-11-18 (PLAN.md step 8, with the decisions made for it).

Code (shared files, behaviour only on Windows):

- `environment.native_resources_dir()` — run from a checkout on Windows, the native app's `windows/QMK Toolbox/Resources/`. Flashers are looked for there after the bundled ones; `libusb_library()` and `driver_installer()` look in the bundled flashers directory first, then there. `avrdude_conf()` gives the native avrdude the shared `common/avrdude.conf`, as the native app does.
- `usb_backend.PyUsbBackend(library)` — loads that libusb; on Windows pyusb would otherwise only search `PATH`. The main window and `tools/watch_devices.py` pass `environment.libusb_library()`. Plain `uv run qmk-toolbox` now works from a checkout on Windows, without the `set` lines of the trial.
- Tools > Install Drivers… (Windows only) — asks, then starts `qmk_driver_installer.exe --all --force drivers.txt` through `ShellExecute` with "runas" (a UAC prompt), as the native app's menu item does. The native app also offers this on its first start; this port does not (the installer offers it instead).
- `app.window_icon()` — the QMK icon on Windows (bundled `.ico`, or the native app's in a checkout); the window had Qt's default icon before.
- Tests for the new lookups and for `PyUsbBackend` with a given library. The bundled-avrdude test now makes its fake `avrdude` executable: since `shutil.which` is used it needs to be on macOS and Linux. It passed on Windows only because Windows treats every file as executable, so **the tests as pushed in 1575bd6 fail that test on macOS and Linux**; this step fixes it.

`packaging/windows/`:

- `build-installer.py` — a venv with the pinned dependencies (`requirements.txt`, resolved for Windows: the same versions as the macOS app, with `pefile` and `pywin32-ctypes` instead of `macholib`), qmk_flashutils 20260711 `windowsX64` checked against `SHA256SUMS` (the value matches the digest GitHub lists for the asset), PyInstaller, a check that the flashers, libusb, driver installer, data and hidapi are in the app, then Inno Setup. About 60 s. Written in Python rather than PowerShell, which would need its script execution policy changed; Python 3.14's `tarfile` reads the `.tar.zst`.
- `qmk-toolbox.spec` — a one-folder app, `qmk-toolbox-qt.exe` with the native app's icon and a version resource ("QMK Toolbox (Qt)", shown in Task Manager and file properties). The eight flashers with their `avrdude.conf`, and the native app's `libusb-1.0.dll`, `qmk_driver_installer.exe` and `drivers.txt`, go in `_internal/qmk_toolbox/flashers/` (qmk_flashutils links libusb into its tools and has no driver installer); the data files and icon in `_internal/qmk_toolbox/data/`.
- `qmk-toolbox.iss` — its own AppId, `Program Files\QMK Toolbox (Qt)`, a Start menu entry, an optional desktop icon, and an "Install drivers" task (ticked by default) that runs the driver installer during setup. "Open with" entries for `.hex`/`.bin` (`OpenWithProgids` and `Applications\qmk-toolbox-qt.exe`), never the default. `qmk:` links only if no other app handles them, or this one already does (decided once when setup starts). An update first deletes `_internal`, so no files of the previous version stay behind. The app started at the end of setup runs as the original user, not elevated.
- The app is 112 MB in 187 files; the installer 33.5 MB.

Verified on the Windows PC (2026-11-18, Smart App Control on):

- 123 tests pass, 2 skipped.
- From a checkout, with no environment variables: libusb, the flashers, `common/avrdude.conf` and the driver installer are found, and the window logs no libusb error.
- The built app, run directly: version 0.3.4 shown (package metadata bundled), no libusb error, the QMK icon in the title bar, and the version resource on the `.exe`.
- Smart App Control let everything run: the locally built app and installer, qmk_flashutils' Windows tools (unsigned; all eight started), and the native app's flashers and libusb. `qmk_driver_installer.exe` requires elevation, so it only runs through UAC.
- **Installed (by the user):** default options, and the app started at the end of setup; the user tried it briefly and reported it working (which functions were tried was not recorded). Afterwards: the files in `C:\Program Files\QMK Toolbox (Qt)`, the Start menu entry, "QMK Toolbox (Qt) 0.3.4" (publisher QMK) in Apps, "Open with" entries for `.hex`/`.bin` with no default changed, and `qmk:` links registered to this app (the native app is not installed on that PC).

Not verified:

- Whether the installer's driver task ran: the drivers were already installed the day before, and installing the same packages again leaves no new driver package.
- Tools > Install Drivers… beyond finding the installer.
- With the installed app: a flash with qmk_flashutils' dfu-programmer in particular; opening a `.hex` from Explorer; a `qmk:` link from a browser; installing over an earlier version; uninstalling.
- A copy downloaded from the internet (SmartScreen, and Smart App Control, which treats downloaded files more strictly); other PCs; Windows 10.
- These changes on macOS and Linux (the tests have not been run there since the Windows trial).

Known limitations:

- **Unsigned** (app and installer). Fine on the PC that built it; a downloaded copy gets SmartScreen warnings and may be blocked by Smart App Control.
- **Not built in CI;** x64 only.
- **No per-device driver check.** The native app logs when a bootloader has the wrong driver; this port does not know which driver a device has.
- **libusb is the native app's copy** (its version is not recorded there); the driver list is the native app's `drivers.txt`, so a new entry there reaches this installer too.
- The installer shows no licence and bundles no licence texts for the flashers (the Linux package's `copyright` lists them).

## Background

- **Flashers.** First decided (2026-11-16) to use the system's, since the binaries in `macos/QMK Toolbox/Resources/` are x86_64-only and do not run on the arm64 development Mac without Rosetta. Revised the same day in step 5: the Linux package bundles qmk_flashutils, and runs from a checkout still use `PATH`. qmk_flashutils also has macOS arm64 builds, should the Mac ever need them. Homebrew on the Mac has `dfu-util` and `dfu-programmer` 1.1.0; the primary test devices use Atmel DFU, so `dfu-programmer` matters most.
- **`dfu-programmer reset` can hang on macOS 27.** After the chip leaves DFU the process often never returns, although the reset worked. The installed native QMK Toolbox on the development Mac is patched with a wrapper script that kills `reset`/`launch` after 5 s and reports success. Handled here in step 2 with a timeout. Homebrew's 1.1.0 build did not hang in two standalone resets, but did hang on the reset after a real flash (2026-11-16), where the timeout recovered as intended.
