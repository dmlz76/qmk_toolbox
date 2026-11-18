import os
import shutil
import socket
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from qmk_toolbox.ui.single_instance import SingleInstance


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def name():
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


def test_second_launch_hands_its_arguments_to_the_first(app, name, monkeypatch):
    first = SingleInstance(name)
    assert not first.forward([])  # nothing running yet
    assert first.listen()
    received = receive(first)

    monkeypatch.setenv("XDG_ACTIVATION_TOKEN", "token-1")
    assert SingleInstance(name).forward(["/home/me/fw.hex"])
    wait_for(received)
    assert received == [(["/home/me/fw.hex"], "token-1")]

    received.clear()
    monkeypatch.delenv("XDG_ACTIVATION_TOKEN")
    assert SingleInstance(name).forward([])
    wait_for(received)
    assert received == [([], "")]


def test_socket_left_behind_by_a_crash_is_replaced(app, name):
    stale = socket.socket(socket.AF_UNIX)
    stale.bind(name)
    stale.close()

    instance = SingleInstance(name)
    assert not instance.forward(["fw.hex"])
    assert instance.listen()
    received = receive(instance)
    assert SingleInstance(name).forward(["fw.hex"])
    wait_for(received)


def test_garbage_is_ignored(app, name):
    instance = SingleInstance(name)
    assert instance.listen()
    received = receive(instance)

    client = socket.socket(socket.AF_UNIX)
    client.connect(name)
    client.sendall(b"not json")
    client.close()
    assert SingleInstance(name).forward(["fw.hex"])
    wait_for(received)
    assert received == [(["fw.hex"], "")]
