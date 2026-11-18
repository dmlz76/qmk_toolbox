# QMK Toolbox for Linux

A third implementation of QMK Toolbox, next to the native macOS and Windows apps, written in Python with PySide6 (Qt 6). It is made for Linux and is released as a Debian package for Ubuntu; it also runs on macOS and Windows, from a checkout or as a locally built app. It mirrors the macOS app's structure, so that changes can be carried across.

Design decisions are in [PLAN.md](PLAN.md); what has been done and verified so far is in [PROGRESS.md](PROGRESS.md).

## Running from source

With [uv](https://docs.astral.sh/uv/), from this directory:

```sh
uv run qmk-toolbox            # optionally followed by a firmware file or a qmk:// link
```

Run like this, the app uses the flashers on `PATH` and logs how to install one that is missing (for example `sudo apt install avrdude dfu-programmer dfu-util teensy-loader-cli`, or Homebrew on macOS). The others are in [qmk_flashutils](https://github.com/qmk/qmk_flashutils). pyusb needs libusb, which Ubuntu already has (`brew install libusb` on macOS).

On Windows the app uses the native Windows app's flashers, `libusb-1.0.dll` and driver installer from `windows/QMK Toolbox/Resources/` in this repository, so there is nothing to install besides uv (and Python 3.14 from python.org if Smart App Control blocks uv's own Python). Bootloaders need WinUSB or libusb drivers: Tools > Install Drivers… installs them.

On Linux, flashing and the HID console without root need [QMK's udev rules](https://github.com/qmk/qmk_udev). The package installs them; without it, install them from that repository. The app logs an error when a bootloader connects that it cannot access.

## Tests

```sh
uv run pytest
```

The tests need no hardware and no display. CI also runs them with Ubuntu's own Python packages, which are the ones the package uses.

## Building the package

On Ubuntu or Debian:

```sh
packaging/linux/build-deb.sh          # -> dist/qmk-toolbox_<version>-1_<arch>.deb; pass arm64 for ARM
sudo apt install ./dist/qmk-toolbox_*.deb
```

The package bundles QMK's own flasher builds (qmk_flashutils) and udev rules (qmk_udev), pinned in the script and checked against [SHA256SUMS](packaging/linux/SHA256SUMS). The Maintainer field comes from `DEBFULLNAME` and `DEBEMAIL`, or else from git config.

## Building the macOS app and the Windows installer

On a Mac, `packaging/macos/build-app.sh` builds `dist/QMK-Toolbox-Qt-<version>-<arch>.dmg`. On Windows, with [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed:

```sh
uv run --no-project --python 3.14 packaging/windows/build-installer.py   # -> dist/QMK-Toolbox-Qt-<version>-x64-setup.exe
```

Both bundle Python, Qt and qmk_flashutils' flashers with PyInstaller, and install as "QMK Toolbox (Qt)" next to the native app without replacing it. Neither is signed for distribution, so they are meant for the machine that built them.
