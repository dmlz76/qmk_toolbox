import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from qmk_toolbox.ui.single_instance import SingleInstance


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def name():
    if sys.platform == "win32":
        # A named pipe, not a file.
        yield f"qmk-toolbox-test-{uuid.uuid4().hex}"
        return
    # Not under tmp_path: on macOS that is too long for a socket path (104 bytes at most).
    directory = tempfile.mkdtemp(prefix="qmk-", dir="/tmp")
    yield os.path.join(directory, "toolbox")
    shutil.rmtree(directory, ignore_errors=True)


def receive(instance):
    received = []
    instance.message_received.connect(lambda arguments, token: received.append((arguments, token)))
    return received


def wait_for(received, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not received:
        assert time.monotonic() < deadline, "timed out"
        QApplication.processEvents()
        time.sleep(0.005)


SRC_DIR = Path(__file__).resolve().parents[1] / "src"

LAUNCH = """
import json, sys
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalSocket
from qmk_toolbox.ui.single_instance import SingleInstance

app = QCoreApplication([])
name, arguments = sys.argv[1], json.loads(sys.argv[2])
if arguments == "garbage":
    client = QLocalSocket()
    client.connectToServer(name)
    client.waitForConnected(1000)
    client.write(b"not json")
    client.waitForBytesWritten(1000)
    client.disconnectFromServer()
    sys.exit(0)
sys.exit(0 if SingleInstance(name).forward(arguments) else 1)
"""


def launch(name, arguments):
    """Starts another process that hands ``arguments`` (or "garbage") to the
    running instance, and handles this one's events until it ends, as a real
    second launch would. (With both ends in one process, Windows' named pipes
    sometimes lose the message.)"""
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(SRC_DIR), os.environ.get("PYTHONPATH", "")]))
    process = subprocess.Popen([sys.executable, "-c", LAUNCH, name, json.dumps(arguments)], env=env)
    deadline = time.monotonic() + 30
    while process.poll() is None:
        assert time.monotonic() < deadline, "timed out"
        QApplication.processEvents()
        time.sleep(0.005)
    return process.returncode == 0


def test_second_launch_hands_its_arguments_to_the_first(app, name, monkeypatch):
    first = SingleInstance(name)
    assert not first.forward([])  # nothing running yet
    assert first.listen()
    received = receive(first)

    monkeypatch.setenv("XDG_ACTIVATION_TOKEN", "token-1")
    assert launch(name, ["/home/me/fw.hex"])
    wait_for(received)
    assert received == [(["/home/me/fw.hex"], "token-1")]

    received.clear()
    monkeypatch.delenv("XDG_ACTIVATION_TOKEN")
    assert launch(name, [])
    wait_for(received)
    assert received == [([], "")]


@pytest.mark.skipif(sys.platform == "win32", reason="a named pipe goes away with its process")
def test_socket_left_behind_by_a_crash_is_replaced(app, name):
    stale = socket.socket(socket.AF_UNIX)
    stale.bind(name)
    stale.close()

    instance = SingleInstance(name)
    assert not instance.forward(["fw.hex"])
    assert instance.listen()
    received = receive(instance)
    assert launch(name, ["fw.hex"])
    wait_for(received)


def test_garbage_is_ignored(app, name):
    instance = SingleInstance(name)
    assert instance.listen()
    received = receive(instance)

    assert launch(name, "garbage")
    assert launch(name, ["fw.hex"])
    wait_for(received)
    assert received == [(["fw.hex"], "")]
