from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from src.events import emit_event
from src.models import AgentResult, Task


async def run_agent(
    *,
    role: str,
    task: Task,
    events_path: Path,
    timeout: float,
) -> AgentResult:
    cmd = [sys.executable, "-m", f"agents.{role}", str(task.id)]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=task.worktree,
    )
    emit_event(events_path, task_id=task.task_number, actor=role, type="agent_started", pid=process.pid)

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        emit_event(
            events_path,
            task_id=task.task_number,
            actor=role,
            type="agent_finished",
            exit_code=-1,
            error="timeout",
        )
        return AgentResult(exit_code=-1, stdout_final="", error=f"timeout after {timeout}s")

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

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
