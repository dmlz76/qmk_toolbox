"""Builds the Windows installer, dist/QMK-Toolbox-Qt-<version>-x64-setup.exe (in qt/).

From qt/:

    uv run --no-project --python 3.14 packaging/windows/build-installer.py

Needs uv and Inno Setup 6 (winget install JRSoftware.InnoSetup). Python, Qt and
the other dependencies are bundled into the app with PyInstaller, at the
versions pinned in requirements.txt. The flashers are QMK's release builds
(qmk_flashutils), pinned below and checked against SHA256SUMS; libusb (for
finding devices) and the driver installer come from the native Windows app in
this repository.

Neither the app nor the installer is signed: Windows SmartScreen warns about
copies downloaded from the internet. One built and run on the same PC is fine.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
import urllib.request
from pathlib import Path

FLASHUTILS_VERSION = "20260711"
PYTHON_VERSION = "3.14"

here = Path(__file__).resolve().parent
project = here.parents[1]
repo = project.parent
native = repo / "windows" / "QMK Toolbox" / "Resources"
downloads = project / "build" / "downloads"
build = project / "build" / "windows-x64"
dist = project / "dist"


def fail(message: str) -> None:
    sys.exit(f"build-installer: {message}")


def run(*command: str | Path, env: dict[str, str] | None = None) -> None:
    subprocess.run([str(part) for part in command], check=True, env=env)


def fetch(url: str, name: str) -> Path:
    """Downloads into ``downloads`` once, and checks the file against SHA256SUMS."""
    path = downloads / name
    if not path.is_file():
        partial = path.with_name(name + ".part")
        with urllib.request.urlopen(url) as response, open(partial, "wb") as out:
            shutil.copyfileobj(response, out)
        partial.replace(path)
    sums = dict(reversed(line.split("  ", 1)) for line in (here / "SHA256SUMS").read_text().splitlines() if line)
    if name not in sums:
        fail(f"no checksum for {name} in SHA256SUMS")
    if hashlib.sha256(path.read_bytes()).hexdigest() != sums[name]:
        fail(f"checksum mismatch for {name}")
    return path


def find_iscc() -> Path:
    candidates = [shutil.which("ISCC")] + [
        os.path.join(base, "Inno Setup 6", "ISCC.exe")
        for base in (
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("ProgramFiles", ""),
        )
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return Path(candidate)
    fail("Inno Setup 6 not found; install it with: winget install JRSoftware.InnoSetup")


def main() -> None:
    if sys.platform != "win32":
        fail("run this on Windows")
    iscc = find_iscc()
    version = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

    shutil.rmtree(build, ignore_errors=True)
    for directory in (downloads, build, dist):
        directory.mkdir(parents=True, exist_ok=True)

    # A Python environment with exactly the pinned dependencies, and the app.
    venv = build / "venv"
    python = venv / "Scripts" / "python.exe"
    run("uv", "venv", "--quiet", "--python", PYTHON_VERSION, venv)
    run("uv", "pip", "install", "--quiet", "--python", python, "--require-hashes", "-r", here / "requirements.txt")
    run("uv", "pip", "install", "--quiet", "--python", python, "--no-deps", project)

    # The flashers, with the avrdude.conf that matches their avrdude.
    name = f"qmk_flashutils-{FLASHUTILS_VERSION}-windowsX64.tar.zst"
    archive = fetch(f"https://github.com/qmk/qmk_flashutils/releases/download/{FLASHUTILS_VERSION}/{name}", name)
    flashers = build / "flashutils"
    with tarfile.open(archive) as tar:
        tar.extractall(flashers, filter="data")

    # The native app's icon, under the name app.window_icon() looks for.
    icon = build / "qmk-toolbox.ico"
    shutil.copyfile(native / "output.ico", icon)

    env = dict(
        os.environ,
        QMK_TOOLBOX_VERSION=version,
        QMK_TOOLBOX_FLASHERS=str(flashers),
        QMK_TOOLBOX_NATIVE_RESOURCES=str(native),
        QMK_TOOLBOX_COMMON=str(repo / "common"),
        QMK_TOOLBOX_ICON=str(icon),
    )
    run(venv / "Scripts" / "pyinstaller.exe", "--noconfirm", "--log-level", "WARN",
        "--distpath", build / "dist", "--workpath", build / "work", here / "qmk-toolbox.spec", env=env)
    app = build / "dist" / "qmk-toolbox-qt"

    # PyInstaller does not fail when it cannot find these, but the app would not work without them.
    package = app / "_internal" / "qmk_toolbox"
    required = [
        app / "qmk-toolbox-qt.exe",
        package / "data" / "mcu-list.txt",
        package / "data" / "qmk-toolbox.ico",
        package / "flashers" / "dfu-programmer.exe",
        package / "flashers" / "avrdude.conf",
        package / "flashers" / "libusb-1.0.dll",
        package / "flashers" / "qmk_driver_installer.exe",
        package / "flashers" / "drivers.txt",
    ]
    for path in required:
        if not path.is_file():
            fail(f"missing from the app: {path.relative_to(app)}")
    if not list((app / "_internal").glob("hid.*.pyd")):
        fail("missing from the app: hidapi (hid.*.pyd)")

    run(iscc, "/Q", f"/DAppVersion={version}", f"/DAppDir={app}", f"/DIconFile={icon}",
        f"/DOutputDir={dist}", here / "qmk-toolbox.iss")
    installer = dist / f"QMK-Toolbox-Qt-{version}-x64-setup.exe"
    if not installer.is_file():
        fail(f"Inno Setup did not produce {installer}")
    print(app)
    print(installer)


if __name__ == "__main__":
    main()
