from __future__ import annotations

import subprocess
import sys

import pytest

from agno_tools.opencode_subprocess import run_opencode_command


def test_run_opencode_command_buffered_matches_subprocess() -> None:
    cmd = [sys.executable, "-c", "print('hello'); print('err', file=__import__('sys').stderr)"]
    rc, text = run_opencode_command(cmd, None, 30.0, stream=False)
    assert rc == 0
    assert "hello" in text
    assert "err" in text


def test_run_opencode_command_stream_preserves_capture(capsys) -> None:
    cmd = [sys.executable, "-c", "import time; print('a'); time.sleep(0.02); print('b')"]
    rc, text = run_opencode_command(cmd, None, 30.0, stream=True)
    assert rc == 0
    assert "a" in text and "b" in text
    out = capsys.readouterr().out
    assert "a" in out and "b" in out


def test_run_opencode_command_stream_timeout() -> None:
    cmd = [sys.executable, "-c", "import time; time.sleep(60)"]
    with pytest.raises(subprocess.TimeoutExpired):
        run_opencode_command(cmd, None, 0.25, stream=True)
