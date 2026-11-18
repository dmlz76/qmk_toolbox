import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from qmk_toolbox.mcu_list import DEFAULT_MCU, load_mcu_list
from qmk_toolbox.message_type import MessageType
from qmk_toolbox.process_runner import ProcessRunner

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_tool(directory: Path, name: str, script: str) -> str:
    """A fake flasher that runs ``script`` with Python. Returns its path."""
    if sys.platform == "win32":
        # Windows has no shebang lines: a batch file runs the script instead.
        (directory / f"{name}.py").write_text(script)
        tool = directory / f"{name}.cmd"
        tool.write_text(f'@"{sys.executable}" "%~dp0{name}.py" %*\n')
        return str(tool)
    tool = directory / name
    tool.write_text(f"#!{sys.executable}\n{script}")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return str(tool)


def same_path(found: str | None, expected: str) -> bool:
    return found is not None and os.path.normcase(found) == os.path.normcase(expected)


def test_streams_stdout_and_stderr_as_typed_lines(tmp_path):
    make_tool(
        tmp_path,
        "flasher",
        "import sys\n"
        "print('args', *sys.argv[1:])\n"
        "sys.stdout.write('10%\\r50%\\r100%\\n\\n')\n"
        "print('oops', file=sys.stderr)\n"
        "sys.exit(3)\n",
    )
    messages = []
    exit_code = ProcessRunner(tool_dirs=[tmp_path]).run("flasher", ["-a", "b c"], lambda m, t: messages.append((m, t)))

    assert exit_code == 3
    assert [m for m, t in messages if t is MessageType.COMMAND_OUTPUT] == ["args -a b c", "10%", "50%", "100%"]
    assert [m for m, t in messages if t is MessageType.COMMAND_ERROR] == ["oops"]


def test_runs_in_the_configured_directory(tmp_path):
    make_tool(tmp_path, "flasher", "import os\nprint(os.getcwd())\n")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    messages = []
    ProcessRunner(tool_dirs=[tmp_path], cwd=data_dir).run("flasher", [], lambda m, t: messages.append(m))
    assert os.path.realpath(messages[0]) == os.path.realpath(data_dir)


def test_relative_tool_dir_works_with_a_different_working_directory(tmp_path, monkeypatch):
    tools, data_dir = tmp_path / "tools", tmp_path / "data"
    tools.mkdir()
    data_dir.mkdir()
    make_tool(tools, "flasher", "print('ran')\n")
    monkeypatch.chdir(tmp_path)

    messages = []
    exit_code = ProcessRunner(tool_dirs=["tools"], cwd=data_dir).run("flasher", [], lambda m, t: messages.append(m))
    assert (exit_code, messages) == (0, ["ran"])


def test_bundled_tools_take_precedence_over_path(tmp_path, monkeypatch):
    bundled, system = tmp_path / "bundled", tmp_path / "system"
    for directory in (bundled, system):
        directory.mkdir()
    bundled_flasher = make_tool(bundled, "flasher", "")
    make_tool(system, "flasher", "")
    other = make_tool(system, "other", "")
    monkeypatch.setenv("PATH", str(system))

    runner = ProcessRunner(tool_dirs=[bundled])
    assert same_path(runner.find_tool("flasher"), bundled_flasher)
    assert same_path(runner.find_tool("other"), other)


def test_missing_tool_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    messages = []
    exit_code = ProcessRunner().run("no-such-flasher", [], lambda m, t: messages.append((m, t)))
    assert exit_code is None
    assert messages == [("Could not find no-such-flasher", MessageType.ERROR)]


def test_install_hint_is_shown_for_a_missing_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    messages = []
    ProcessRunner(install_hint=lambda tool: f"get {tool}").run("flasher", [], lambda m, t: messages.append(m))
    assert messages == ["Could not find flasher", "get flasher"]


def test_hung_process_is_killed_after_the_timeout(tmp_path):
    # Short: on Windows only the batch file is killed, and its Python child keeps the pipes open until it exits.
    make_tool(tmp_path, "flasher", "import time\nprint('resetting', flush=True)\ntime.sleep(4)\n")
    messages = []
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        ProcessRunner(tool_dirs=[tmp_path]).run("flasher", [], lambda m, t: messages.append(m), timeout=1)
    assert time.monotonic() - started < 10
    assert messages == ["resetting"]


def test_timeout_does_not_affect_a_process_that_finishes(tmp_path):
    make_tool(tmp_path, "flasher", "print('done')\n")
    messages = []
    assert ProcessRunner(tool_dirs=[tmp_path]).run("flasher", [], lambda m, t: messages.append(m), timeout=30) == 0
    assert messages == ["done"]


def test_mcu_list():
    mcus = load_mcu_list(REPO_ROOT / "common/mcu-list.txt")
    assert ("atmega32u4", "ATmega32U4") in mcus
    assert DEFAULT_MCU in dict(mcus)
    assert all(key and name for key, name in mcus)
