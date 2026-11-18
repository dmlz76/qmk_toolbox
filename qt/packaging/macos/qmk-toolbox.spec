# PyInstaller spec for the macOS app. Run by build-app.sh, which sets the
# QMK_TOOLBOX_* variables below; not meant to be run on its own.
import os

from PyInstaller.utils.hooks import copy_metadata

APP_NAME = "QMK Toolbox (Qt)"
# Not the native app's fm.qmk.toolbox, so that the two can be installed side by side.
BUNDLE_ID = "fm.qmk.toolbox.qt"

version = os.environ["QMK_TOOLBOX_VERSION"]
flashers = os.environ["QMK_TOOLBOX_FLASHERS"]
common = os.environ["QMK_TOOLBOX_COMMON"]
icon = os.environ["QMK_TOOLBOX_ICON"]

FLASHER_TOOLS = ["avrdude", "bootloadHID", "dfu-programmer", "dfu-util", "hid_bootloader_cli",
                 "mdloader", "teensy_loader_cli", "wb32-dfu-updater_cli"]

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    # Found by environment.flashers_dir() and data_dir(), next to the package's modules.
    binaries=[(os.path.join(flashers, tool), "qmk_toolbox/flashers") for tool in FLASHER_TOOLS],
    datas=[
        (os.path.join(flashers, "avrdude.conf"), "qmk_toolbox/flashers"),
        (os.path.join(common, "mcu-list.txt"), "qmk_toolbox/data"),
        (os.path.join(common, "reset.eep"), "qmk_toolbox/data"),
        (os.path.join(common, "reset_left.eep"), "qmk_toolbox/data"),
        (os.path.join(common, "reset_right.eep"), "qmk_toolbox/data"),
        # The app reads its version from its package metadata.
        *copy_metadata("qmk-toolbox"),
    ],
    # Imported by name at run time, so not found by PyInstaller's import scan:
    # hidapi by hid/hid_backend.py, the libusb backend by pyusb.
    hiddenimports=["hid", "usb.backend.libusb1"],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="qmk-toolbox",
    console=False,
    # Files and qmk: links arrive as Qt FileOpen events; argv emulation would swallow them.
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="qmk-toolbox")

_hex_type = "fm.qmk.hex"
app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=icon,
    bundle_identifier=BUNDLE_ID,
    version=version,
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSApplicationCategoryType": "public.app-category.utilities",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright 2024 QMK",
        # Same types and URL scheme as the native app. "Alternate", so that while
        # both are installed the native app stays the default for .hex/.bin files.
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Intel HEX firmware",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": [_hex_type],
            },
            {
                "CFBundleTypeName": "Binary firmware",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["com.apple.macbinary-archive"],
            },
        ],
        # The native app exports this type; declaring it here too keeps .hex
        # files recognised once that app is removed.
        "UTImportedTypeDeclarations": [
            {
                "UTTypeIdentifier": _hex_type,
                "UTTypeDescription": "Intel HEX firmware",
                "UTTypeConformsTo": ["public.data"],
                "UTTypeTagSpecification": {"public.filename-extension": ["hex"]},
            },
        ],
        "CFBundleURLTypes": [
            {
                "CFBundleTypeRole": "Viewer",
                "CFBundleURLName": f"{BUNDLE_ID}.open",
                "CFBundleURLSchemes": ["qmk"],
            },
        ],
    },
)
