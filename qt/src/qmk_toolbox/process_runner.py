from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Iterable, TextIO

from .message_type import MessageType

Output = Callable[[str, MessageType], None]


class ProcessRunner:
    """Runs a flasher CLI and streams its output line by line as typed messages.

    ``tool_dirs`` are searched first (bundled binaries), then ``PATH`` (system
    packages). ``cwd`` is the working directory for the tools.

    ``install_hint`` maps a tool name to advice on how to install it, shown
    when the tool is missing.

    ``run`` blocks until the process exits, so call it off the UI thread. The
    output callback is invoked from reader threads.
    """

    def __init__(
        self,
        tool_dirs: Iterable[str | Path] = (),
        cwd: str | Path | None = None,
        install_hint: Callable[[str], str | None] | None = None,
    ):
        self.install_hint = install_hint
        # Absolute, because the process is started with a different working directory.
        self.tool_dirs = [Path(d).absolute() for d in tool_dirs]
        self.cwd = str(cwd) if cwd is not None else None

    def find_tool(self, command: str) -> str | None:
        # which() also finds "avrdude.exe" for "avrdude" on Windows.
        for directory in self.tool_dirs:
            found = shutil.which(command, path=str(directory))
            if found is not None:
                return found
        return shutil.which(command)

    def run(self, command: str, args: list[str], output: Output, timeout: float | None = None) -> int | None:
        """Returns the exit code, or ``None`` if the process could not be started.

        If ``timeout`` (seconds) elapses first, the process is killed and
        ``subprocess.TimeoutExpired`` is raised.
        """
        executable = self.find_tool(command)
        if executable is None:
            output(f"Could not find {command}", MessageType.ERROR)
            hint = self.install_hint(command) if self.install_hint else None
            if hint:
                output(hint, MessageType.ERROR)
            return None

        try:
            process = subprocess.Popen(
                [executable, *args],
                cwd=self.cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # Text mode with universal newlines, so that progress bars
                # redrawn with a bare \r come through as separate lines.
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as error:
            output(str(error), MessageType.ERROR)
            return None

        readers = [
            threading.Thread(target=_pump, args=(process.stdout, output, MessageType.COMMAND_OUTPUT)),
            threading.Thread(target=_pump, args=(process.stderr, output, MessageType.COMMAND_ERROR)),
        ]
        for reader in readers:
            reader.start()
        try:
            return process.wait(timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
        finally:
            for reader in readers:
                reader.join()


def _pump(stream: TextIO, output: Output, message_type: MessageType) -> None:
    with stream:
        for line in stream:
            line = line.rstrip("\n")
            if line:
                output(line, message_type)
