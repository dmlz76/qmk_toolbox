# PyInstaller spec for the Windows app. Run by build-installer.py, which sets
# the QMK_TOOLBOX_* variables below; not meant to be run on its own.
import os

from PyInstaller.utils.hooks import copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

APP_NAME = "QMK Toolbox (Qt)"
# Not the native app's qmk_toolbox.exe, so that the two can be installed side by side.
EXE_NAME = "qmk-toolbox-qt"

version = os.environ["QMK_TOOLBOX_VERSION"]
flashers = os.environ["QMK_TOOLBOX_FLASHERS"]
native = os.environ["QMK_TOOLBOX_NATIVE_RESOURCES"]
common = os.environ["QMK_TOOLBOX_COMMON"]
icon = os.environ["QMK_TOOLBOX_ICON"]

FLASHER_TOOLS = ["avrdude", "bootloadHID", "dfu-programmer", "dfu-util", "hid_bootloader_cli",
                 "mdloader", "teensy_loader_cli", "wb32-dfu-updater_cli"]

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    # Found by environment.flashers_dir() and data_dir(), next to the package's
    # modules. libusb and the driver installer come from the native Windows app,
    # since qmk_flashutils links libusb into its tools and has no installer.
    binaries=[
        *[(os.path.join(flashers, f"{tool}.exe"), "qmk_toolbox/flashers") for tool in FLASHER_TOOLS],
        (os.path.join(native, "libusb-1.0.dll"), "qmk_toolbox/flashers"),
        (os.path.join(native, "qmk_driver_installer.exe"), "qmk_toolbox/flashers"),
    ],
    datas=[
        (os.path.join(flashers, "avrdude.conf"), "qmk_toolbox/flashers"),
        (os.path.join(native, "drivers.txt"), "qmk_toolbox/flashers"),
        (os.path.join(common, "mcu-list.txt"), "qmk_toolbox/data"),
        (os.path.join(common, "reset.eep"), "qmk_toolbox/data"),
        (os.path.join(common, "reset_left.eep"), "qmk_toolbox/data"),
        (os.path.join(common, "reset_right.eep"), "qmk_toolbox/data"),
        # The window icon (app.window_icon()); the same icon as the .exe file's.
        (icon, "qmk_toolbox/data"),
        # The app reads its version from its package metadata.
        *copy_metadata("qmk-toolbox"),
    ],
    # Imported by name at run time, so not found by PyInstaller's import scan:
    # hidapi by hid/hid_backend.py, the libusb backend by pyusb.
    hiddenimports=["hid", "usb.backend.libusb1"],
    excludes=["tkinter"],
)

# Shown by Windows in Task Manager, file properties and "Open with".
numbers = tuple(int(part) for part in version.split(".")) + (0,) * (4 - len(version.split(".")))
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("CompanyName", "QMK"),
            StringStruct("FileDescription", APP_NAME),
            StringStruct("FileVersion", version),
            StringStruct("InternalName", EXE_NAME),
            StringStruct("LegalCopyright", "Copyright 2024 QMK"),
            StringStruct("OriginalFilename", f"{EXE_NAME}.exe"),
            StringStruct("ProductName", APP_NAME),
            StringStruct("ProductVersion", version),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=EXE_NAME,
    console=False,
    icon=icon,
    version=version_info,
)
coll = COLLECT(exe, a.binaries, a.datas, name=EXE_NAME)
