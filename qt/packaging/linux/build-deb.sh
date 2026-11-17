#!/bin/sh
# Builds the Debian/Ubuntu package, dist/qmk-toolbox_<version>-1_<arch>.deb (in qt/).
#
#   packaging/linux/build-deb.sh [amd64|arm64]      default: this machine's architecture
#
# Needs uv, curl, tar with zstd, python3 and dpkg-deb. The flashers
# (qmk_flashutils) and the udev rules with their helper (qmk_udev) are QMK's
# release builds, pinned below and checked against SHA256SUMS. The package's
# Maintainer field comes from DEBFULLNAME and DEBEMAIL, or else from git config.
set -eu

FLASHUTILS_VERSION=20260711
QMK_UDEV_VERSION=v0.1.23

here=$(cd "$(dirname "$0")" && pwd)
project=$(cd "$here/../.." && pwd)
repo=$(cd "$project/.." && pwd)

arch=${1:-$(dpkg --print-architecture)}
case $arch in
    amd64) qmk_arch=linuxX64 ;;
    arm64) qmk_arch=linuxARM64 ;;
    *) echo "Unsupported architecture: $arch" >&2; exit 1 ;;
esac

version=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$project/pyproject.toml")
maintainer_name=${DEBFULLNAME:-$(git config user.name || true)}
maintainer_email=${DEBEMAIL:-$(git config user.email || true)}
if [ -z "$maintainer_name" ] || [ -z "$maintainer_email" ]; then
    echo "Set DEBFULLNAME and DEBEMAIL for the package's Maintainer field" >&2
    exit 1
fi

downloads=$project/build/downloads
build=$project/build/deb-$arch
root=$build/root
lib=$root/usr/lib/qmk-toolbox
umask 022
rm -rf "$build"
mkdir -p "$downloads" "$root/DEBIAN" "$lib" "$project/dist"

# fetch URL NAME: download into $downloads once, and check it against SHA256SUMS.
fetch() {
    if [ ! -f "$downloads/$2" ]; then
        curl -fsSL -o "$downloads/$2.part" "$1"
        mv "$downloads/$2.part" "$downloads/$2"
    fi
    grep "  $2\$" "$here/SHA256SUMS" > "$build/checksum" || { echo "No checksum for $2 in SHA256SUMS" >&2; exit 1; }
    (cd "$downloads" && sha256sum --quiet -c "$build/checksum")
}

# The app, unpacked from its wheel so that the version is known at run time.
uv build --quiet --wheel --out-dir "$build/wheel" "$project"
python3 -m zipfile -e "$build"/wheel/qmk_toolbox-"$version"-*.whl "$lib"
mkdir "$lib/qmk_toolbox/data"
cp "$repo"/common/mcu-list.txt "$repo"/common/reset*.eep "$lib/qmk_toolbox/data/"

# The flashers, with the avrdude.conf that matches their avrdude.
flashutils=qmk_flashutils-$FLASHUTILS_VERSION-$qmk_arch.tar.zst
fetch "https://github.com/qmk/qmk_flashutils/releases/download/$FLASHUTILS_VERSION/$flashutils" "$flashutils"
mkdir "$build/flashutils" "$lib/qmk_toolbox/flashers"
tar -I zstd -xf "$downloads/$flashutils" -C "$build/flashutils"
for tool in avrdude bootloadHID dfu-programmer dfu-util hid_bootloader_cli mdloader teensy_loader_cli \
        wb32-dfu-updater_cli; do
    install -m 755 "$build/flashutils/$tool" "$lib/qmk_toolbox/flashers/"
done
install -m 644 "$build/flashutils/avrdude.conf" "$build/flashutils/flashutils_release_$qmk_arch" \
    "$lib/qmk_toolbox/flashers/"

# udev rules giving the logged-in user access to bootloaders and QMK's HID
# endpoints, and keeping ModemManager away from serial bootloaders.
fetch "https://github.com/qmk/qmk_udev/releases/download/$QMK_UDEV_VERSION/qmk_id-$qmk_arch" \
    "qmk_id-$QMK_UDEV_VERSION-$qmk_arch"
fetch "https://github.com/qmk/qmk_udev/releases/download/$QMK_UDEV_VERSION/50-qmk.rules" \
    "50-qmk-$QMK_UDEV_VERSION.rules"
install -D -m 755 "$downloads/qmk_id-$QMK_UDEV_VERSION-$qmk_arch" "$root/usr/lib/udev/qmk_id"
install -D -m 644 "$downloads/50-qmk-$QMK_UDEV_VERSION.rules" "$root/usr/lib/udev/rules.d/50-qmk.rules"

# Desktop integration.
install -D -m 755 "$here/launcher.py" "$root/usr/bin/qmk-toolbox"
install -D -m 644 "$here/qmk-toolbox.desktop" "$root/usr/share/applications/qmk-toolbox.desktop"
install -D -m 644 "$here/qmk-toolbox-mime.xml" "$root/usr/share/mime/packages/qmk-toolbox.xml"
icons="$repo/macos/QMK Toolbox/Assets.xcassets/AppIcon.appiconset"
for size in 16 32 64 128 256 512; do
    case $size in
        64) source="$icons/icon-32x32@2x.png" ;;
        *) source="$icons/icon-${size}x${size}.png" ;;
    esac
    install -D -m 644 "$source" "$root/usr/share/icons/hicolor/${size}x$size/apps/qmk-toolbox.png"
done
install -D -m 644 "$here/copyright" "$root/usr/share/doc/qmk-toolbox/copyright"

install -m 755 "$here/postinst" "$here/prerm" "$root/DEBIAN/"
depends="python3 (>= 3.10), python3-pyside6.qtwidgets, python3-pyside6.qtnetwork, python3-usb, python3-serial"
depends="$depends, python3-hid, libusb-1.0-0, qt6-wayland | qt6-qpa-plugins"
cat > "$root/DEBIAN/control" <<EOF
Package: qmk-toolbox
Version: $version-1
Architecture: $arch
Maintainer: $maintainer_name <$maintainer_email>
Installed-Size: $(du -sk --exclude=DEBIAN "$root" | cut -f1)
Depends: $depends
Recommends: qt6-wayland, qt6-qpa-plugins
Section: electronics
Priority: optional
Homepage: https://qmk.fm/toolbox
Description: flashing and debugging utility for keyboards running QMK Firmware
 Detects keyboards in bootloader mode and flashes firmware to them, and shows
 the output of their HID console. Includes a key tester.
 .
 Bundles the flashers from qmk_flashutils $FLASHUTILS_VERSION and the udev
 rules from qmk_udev $QMK_UDEV_VERSION.
EOF

deb=$project/dist/qmk-toolbox_$version-1_$arch.deb
dpkg-deb --root-owner-group --build "$root" "$deb" >/dev/null
echo "$deb"
