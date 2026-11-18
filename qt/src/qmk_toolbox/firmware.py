"""Firmware files: which ones are accepted, and fetching them from qmk:// links."""

from __future__ import annotations

import os
import tempfile
import urllib.request
from urllib.request import url2pathname
from pathlib import Path
from urllib.parse import unquote, urlparse

FIRMWARE_EXTENSIONS = (".hex", ".bin")


def is_firmware_file(path: str) -> bool:
    return path.lower().endswith(FIRMWARE_EXTENSIONS)


def local_path(path: str) -> str:
    """The path in a local ``file:`` URL, as desktop environments pass files; anything else unchanged."""
    if path.startswith("file:"):
        parsed = urlparse(path)
        if parsed.netloc in ("", "localhost"):
            # url2pathname also turns "/C:/Users/..." into "C:\Users\..." on Windows.
            return url2pathname(parsed.path)
    return path


def unwrap_qmk_url(url: str) -> str | None:
    """``qmk://https://host/fw.hex`` (or ``qmk:https://...``) -> the inner URL.

    Returns ``None`` if ``url`` is not a qmk link.
    """
    for prefix in ("qmk://", "qmk:"):
        if url.startswith(prefix):
            inner = url[len(prefix):]
            # Qt reads "https:" in "qmk://https://..." as a host with an empty
            # port and drops the colon, so links macOS hands over through Qt
            # arrive as "qmk://https//...". Put it back.
            for scheme in ("https", "http"):
                if inner.startswith(scheme + "//"):
                    return f"{scheme}://{inner[len(scheme) + 2:]}"
            return inner
    return None


def download_firmware(url: str, dest_dir: str | Path, timeout: float = 30.0) -> Path:
    """Download a firmware file into ``dest_dir`` and return its path.

    Raises ``ValueError`` for anything that is not an http(s) link to a
    .hex/.bin file, and ``OSError`` if the download fails.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https links can be downloaded")
    name = os.path.basename(unquote(parsed.path))
    if not is_firmware_file(name):
        raise ValueError("Only .hex and .bin files can be downloaded")

    dest_dir = Path(dest_dir)
    dest_file = dest_dir / name
    request = urllib.request.Request(url, headers={"User-Agent": "QMK Toolbox"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        # Download next to the destination, so a failed download leaves no partial file behind.
        with tempfile.NamedTemporaryFile(dir=dest_dir, prefix=name, suffix=".part", delete=False) as partial:
            try:
                while chunk := response.read(65536):
                    partial.write(chunk)
                partial.close()
                os.replace(partial.name, dest_file)
            except BaseException:
                partial.close()
                os.unlink(partial.name)
                raise
    return dest_file
