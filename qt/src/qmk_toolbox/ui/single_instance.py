from __future__ import annotations

import getpass
import json
import os
import sys

from PySide6.QtCore import QObject, QStandardPaths, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

TIMEOUT_MS = 1000


def default_server_name() -> str:
    # The runtime directory is private to the user; elsewhere Qt puts the
    # socket in the temporary directory, so the name includes the user.
    # On Windows the name is a named pipe's, which cannot hold a path.
    runtime_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation)
    if runtime_dir and sys.platform != "win32":
        return os.path.join(runtime_dir, "qmk-toolbox")
    return f"qmk-toolbox-{getpass.getuser()}"


class SingleInstance(QObject):
    """Keeps one QMK Toolbox running per user, as the Windows app does.

    A second launch (e.g. opening a firmware file from the file manager)
    hands its arguments to the running instance with ``forward`` and exits.
    """

    # The other launch's arguments, and its Wayland activation token (or "").
    message_received = Signal(list, str)

    def __init__(self, name: str | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.name = name or default_server_name()
        self._server: QLocalServer | None = None

    def forward(self, arguments: list[str]) -> bool:
        """Hands ``arguments`` to the running instance. False if there is none."""
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(TIMEOUT_MS):
            return False
        message = {"arguments": arguments, "activation_token": os.environ.get("XDG_ACTIVATION_TOKEN", "")}
        socket.write((json.dumps(message) + "\n").encode())
        socket.flush()
        socket.waitForBytesWritten(TIMEOUT_MS)
        # Wait for the running instance to close the connection once it has
        # read the message: on Windows, whatever it has not read yet when this
        # end disconnects is lost.
        if not socket.waitForDisconnected(TIMEOUT_MS):
            socket.disconnectFromServer()
        return True

    def listen(self) -> bool:
        server = QLocalServer(self)
        server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        # A socket left behind by an instance that crashed would block listening.
        QLocalServer.removeServer(self.name)
        if not server.listen(self.name):
            return False
        server.newConnection.connect(self._accept)
        self._server = server
        return True

    def _accept(self) -> None:
        while (socket := self._server.nextPendingConnection()) is not None:
            # The other launch writes one line straight away, so this does not
            # hold up the UI. Closing the connection tells it the line was read.
            data = socket.readAll().data()
            while not data.endswith(b"\n") and socket.waitForReadyRead(TIMEOUT_MS):
                data += socket.readAll().data()
            socket.disconnectFromServer()
            socket.deleteLater()
            try:
                message = json.loads(data)
                arguments = [str(argument) for argument in message["arguments"]]
                token = str(message.get("activation_token") or "")
            except (ValueError, KeyError, TypeError):
                continue
            self.message_received.emit(arguments, token)
