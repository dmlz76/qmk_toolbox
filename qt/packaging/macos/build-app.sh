#!/bin/sh
# Builds the macOS app, dist/QMK-Toolbox-Qt-<version>-<arch>.dmg (in qt/), for
# this Mac's architecture (arm64 or x86_64).
#
#   packaging/macos/build-app.sh
#
# Needs uv, curl, iconutil and hdiutil (the last two come with macOS), and
# libusb (brew install libusb), which PyInstaller copies into the app. Python,
# Qt and the other dependencies are bundled into the app with PyInstaller, at
# the versions pinned in requirements.txt. The flashers are QMK's release
# builds (qmk_flashutils), pinned below and checked against SHA256SUMS.
#
# The app is signed ad hoc, which is enough on the Mac that built it. A copy
# downloaded elsewhere would need a Developer ID signature and notarization.
set -eu

FLASHUTILS_VERSION=20260711
PYTHON_VERSION=3.14
APP_NAME="QMK Toolbox (Qt)"

here=$(cd "$(dirname "$0")" && pwd)
project=$(cd "$here/../.." && pwd)
repo=$(cd "$project/.." && pwd)

arch=$(uname -m)
case $arch in
    arm64) qmk_arch=macosARM64 ;;
    x86_64) qmk_arch=macosX64 ;;
    *) echo "Unsupported architecture: $arch" >&2; exit 1 ;;
esac

version=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$project/pyproject.toml")
downloads=$project/build/downloads
build=$project/build/macos-$arch
umask 022
rm -rf "$build"
mkdir -p "$downloads" "$build" "$project/dist"

# fetch URL NAME: download into $downloads once, and check it against SHA256SUMS.
fetch() {
    if [ ! -f "$downloads/$2" ]; then
        curl -fsSL -o "$downloads/$2.part" "$1"
        mv "$downloads/$2.part" "$downloads/$2"
    fi
    grep "  $2\$" "$here/SHA256SUMS" > "$build/checksum" || { echo "No checksum for $2 in SHA256SUMS" >&2; exit 1; }
    (cd "$downloads" && shasum -a 256 -s -c "$build/checksum") || { echo "Checksum mismatch for $2" >&2; exit 1; }
}

# A Python environment with exactly the pinned dependencies, and the app.
uv venv --quiet --python "$PYTHON_VERSION" "$build/venv"
python=$build/venv/bin/python
uv pip install --quiet --python "$python" --require-hashes -r "$here/requirements.txt"
uv pip install --quiet --python "$python" --no-deps "$project"

# The flashers, with the avrdude.conf that matches their avrdude. Python 3.14's
# tarfile reads zstd, which the tar that comes with macOS may not.
flashutils=qmk_flashutils-$FLASHUTILS_VERSION-$qmk_arch.tar.zst
fetch "https://github.com/qmk/qmk_flashutils/releases/download/$FLASHUTILS_VERSION/$flashutils" "$flashutils"
"$python" -c 'import sys, tarfile; tarfile.open(sys.argv[1]).extractall(sys.argv[2], filter="data")' \
    "$downloads/$flashutils" "$build/flashutils"

# The icon, from the native app's asset catalogue (same file names as an iconset).
mkdir "$build/AppIcon.iconset"
for png in "$repo/macos/QMK Toolbox/Assets.xcassets/AppIcon.appiconset"/icon-*.png; do
    name=$(basename "$png")
    cp "$png" "$build/AppIcon.iconset/icon_${name#icon-}"
done
iconutil -c icns -o "$build/AppIcon.icns" "$build/AppIcon.iconset"

QMK_TOOLBOX_VERSION=$version \
QMK_TOOLBOX_FLASHERS=$build/flashutils \
QMK_TOOLBOX_COMMON=$repo/common \
QMK_TOOLBOX_ICON=$build/AppIcon.icns \
    "$build/venv/bin/pyinstaller" --noconfirm --log-level WARN \
        --distpath "$build/dist" --workpath "$build/work" "$here/qmk-toolbox.spec"
app=$build/dist/$APP_NAME.app

# PyInstaller does not fail when it cannot find these, but the app would not work without them.
for file in libusb-1.0.dylib hid.cpython-*.so qmk_toolbox/flashers/dfu-programmer qmk_toolbox/data/mcu-list.txt; do
    ls "$app/Contents/Frameworks/"$file >/dev/null 2>&1 || { echo "Missing from the app: $file" >&2; exit 1; }
done
# Everything the app loads must be inside it or part of macOS.
find "$app" -type f \( -perm -u+x -o -name '*.dylib' -o -name '*.so' \) | while read -r file; do
    if otool -L "$file" 2>/dev/null | tail -n +2 | grep -v -E '^\s+(@rpath/|@loader_path/|@executable_path/|/usr/lib/|/System/)' | grep -q .; then
        echo "Links to a library outside the app and macOS: $file" >&2
        exit 1
    fi
done
codesign --verify --deep --strict "$app"

# A disk image to drag the app from into Applications.
mkdir "$build/dmg"
cp -R "$app" "$build/dmg/"
ln -s /Applications "$build/dmg/Applications"
dmg=$project/dist/QMK-Toolbox-Qt-$version-$arch.dmg
rm -f "$dmg"
hdiutil create -quiet -fs HFS+ -volname "$APP_NAME" -srcfolder "$build/dmg" -format UDZO "$dmg"
echo "$app"
echo "$dmg"
