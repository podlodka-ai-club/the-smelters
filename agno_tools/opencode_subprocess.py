"""Run ``opencode`` CLI subprocesses with optional live stdout/stderr forwarding."""

from __future__ import annotations

import subprocess
import sys
import threading
from typing import List, Optional


def run_opencode_command(
    cmd: List[str],
    cwd: Optional[str],
    timeout_secs: float,
    *,
    stream: bool,
) -> tuple[int, str]:
    """Run an opencode command; return ``(returncode, combined_stdout_stderr)``.

    When ``stream`` is True, copy child combined output to ``sys.stdout`` as it arrives
    while still building the full transcript for callers.
    """
    run_kw: dict = {"text": True, "capture_output": True, "timeout": timeout_secs, "check": False}
    popen_kw: dict = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True}
    if cwd:
        run_kw["cwd"] = cwd
        popen_kw["cwd"] = cwd

    if not stream:
        completed = subprocess.run(cmd, **run_kw)
        return completed.returncode, (completed.stdout or "") + (completed.stderr or "")

    proc = subprocess.Popen(cmd, **popen_kw)
    collected: list[str] = []
    lock = threading.Lock()

    def _reader() -> None:
        try:
            if proc.stdout is None:
                return
            while True:
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                with lock:
                    collected.append(chunk)
                sys.stdout.write(chunk)
                sys.stdout.flush()
        finally:
            try:
                if proc.stdout:
                    proc.stdout.close()
            except OSError:
                pass

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    try:
        proc.wait(timeout=timeout_secs)
    except subprocess.TimeoutExpired:
        proc.kill()
        reader.join(timeout=30.0)
        raise subprocess.TimeoutExpired(cmd, timeout_secs) from None
    reader.join(timeout=30.0)
    with lock:
        text = "".join(collected)
    return proc.returncode or 0, text
