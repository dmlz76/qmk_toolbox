import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from qmk_toolbox import firmware


def test_is_firmware_file():
    assert firmware.is_firmware_file("/tmp/fw.hex")
    assert firmware.is_firmware_file("FW.BIN")
    assert not firmware.is_firmware_file("fw.hex.txt")
    assert not firmware.is_firmware_file("")


def test_local_path():
    assert firmware.local_path("file:///home/me/My%20Board.hex") == "/home/me/My Board.hex"
    assert firmware.local_path("file://localhost/tmp/fw.bin") == "/tmp/fw.bin"
    assert firmware.local_path("/tmp/fw.bin") == "/tmp/fw.bin"
    assert firmware.local_path("file://server/share/fw.bin") == "file://server/share/fw.bin"


def test_unwrap_qmk_url():
    assert firmware.unwrap_qmk_url("qmk://https://example.com/fw.hex") == "https://example.com/fw.hex"
    assert firmware.unwrap_qmk_url("qmk:https://example.com/fw.hex") == "https://example.com/fw.hex"
    assert firmware.unwrap_qmk_url("/home/me/fw.hex") is None
    assert firmware.unwrap_qmk_url("https://example.com/fw.hex") is None


def test_unwrap_qmk_url_as_qt_passes_it_on():
    from PySide6.QtCore import QUrl

    for link in ("qmk://https://example.com/fw.hex", "qmk://http://example.com/fw.hex"):
        through_qt = QUrl(link).toString(QUrl.ComponentFormattingOption.FullyEncoded)
        assert firmware.unwrap_qmk_url(through_qt) == link[len("qmk://"):]


@pytest.fixture
def server(tmp_path):
    served = tmp_path / "served"
    served.mkdir()
    (served / "my fw.hex").write_bytes(b":00000001FF\n")
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(served))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_download(server, tmp_path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "my fw.hex").write_bytes(b"old")

    path = firmware.download_firmware(f"{server}/my%20fw.hex", downloads)
    assert path == downloads / "my fw.hex"
    assert path.read_bytes() == b":00000001FF\n"
    assert [p.name for p in downloads.iterdir()] == ["my fw.hex"]


def test_failed_download_leaves_nothing_behind(server, tmp_path):
    with pytest.raises(OSError):
        firmware.download_firmware(f"{server}/missing.hex", tmp_path / "served" / "..")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["served"]


@pytest.mark.parametrize("url", [
    "file:///etc/passwd.hex",
    "ftp://example.com/fw.hex",
    "https://example.com/setup.exe",
    "https://example.com/",
])
def test_download_rejects_other_links(url, tmp_path):
    with pytest.raises(ValueError):
        firmware.download_firmware(url, tmp_path)
    assert list(tmp_path.iterdir()) == []
