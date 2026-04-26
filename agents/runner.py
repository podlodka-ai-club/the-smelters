from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

from src.events import emit_event
from src.models import AgentResult, Task


def _get_python_executable() -> str:
    """Get the Python executable to use for running agents."""
    venv_python = Path(__file__).parent.parent / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


async def run_agent(
    *,
    role: str,
    task: Task,
    events_path: Path,
    timeout: float,
) -> AgentResult:
    cmd = [_get_python_executable(), "-m", f"agents.{role}", str(task.id)]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=task.worktree,
        env=env,
    )
    emit_event(events_path, task_id=task.task_number, actor=role, type="agent_started", pid=process.pid)

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    async def _drain_pipe(
        pipe: asyncio.StreamReader | None,
        *,
        sink: list[str],
        stream_name: str,
    ) -> None:
        if pipe is None:
            return
        while True:
            line_bytes = await pipe.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
            sink.append(line)
            print(f"[{role}/{stream_name}] {line}", file=sys.stderr, flush=True)

    stdout_task = asyncio.create_task(
        _drain_pipe(process.stdout, sink=stdout_lines, stream_name="stdout")
    )
    stderr_task = asyncio.create_task(
        _drain_pipe(process.stderr, sink=stderr_lines, stream_name="stderr")
    )

    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        emit_event(
            events_path,
            task_id=task.task_number,
            actor=role,
            type="agent_finished",
            exit_code=-1,
            error="timeout",
        )
        return AgentResult(exit_code=-1, stdout_final="", error=f"timeout after {timeout}s")

    await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

    stdout = "\n".join(stdout_lines)
    stderr = "\n".join(stderr_lines)

    final_line = ""
    for line in reversed(stdout.splitlines()):
        if line.strip():
            final_line = line
            break

    exit_code = process.returncode if process.returncode is not None else -1
    emit_event(
        events_path,
        task_id=task.task_number,
        actor=role,
        type="agent_finished",
        exit_code=exit_code,
        summary=final_line[:200],
    )
    return AgentResult(
        exit_code=exit_code,
        stdout_final=final_line,
        error=stderr.strip() if exit_code != 0 else None,
    )
