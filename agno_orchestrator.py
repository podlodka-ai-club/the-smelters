import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agno.db.sqlite import SqliteDb
from agno.workflow import Workflow
from agno.workflow.condition import Condition
from agno.workflow.loop import Loop
from agno.workflow.step import Step
from agno.workflow.types import HumanReview, OnReject, StepInput, StepOutput

from src.events import emit_event


MAX_FIX_ITERATIONS = 4
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_S = 2.0


_EPHEMERAL_DB_PATH: Optional[str] = None


def _ephemeral_db() -> SqliteDb:
    """SQLite for session metrics. Uses a per-process temp file so multiple
    connections see the same database (`:memory:` would give each connection
    its own empty DB and break session lookups). File is unlinked on exit."""
    global _EPHEMERAL_DB_PATH
    if _EPHEMERAL_DB_PATH is None:
        import atexit
        import tempfile
        f = tempfile.NamedTemporaryFile(prefix="agno-orchestrator-", suffix=".sqlite", delete=False)
        f.close()
        _EPHEMERAL_DB_PATH = f.name

        def _cleanup(p: str = _EPHEMERAL_DB_PATH) -> None:
            try:
                os.unlink(p)
            except OSError:
                pass

        atexit.register(_cleanup)
    return SqliteDb(db_file=_EPHEMERAL_DB_PATH)

from agno_agents.android_coder import make_android_coder
from agno_agents.code_checker import make_code_checker
from agno_agents.impl_agent import make_impl_agent
from agno_agents.lint_fix_agent import make_lint_fix_agent
from agno_agents.test_case_agent import make_test_case_agent
from agno_agents.test_run_agent import make_test_run_agent
from agno_agents.test_writer_agent import make_test_writer_agent
from agno_tools.claude_code_step import (
    get_claude_run_costs,
    make_claude_code_checker_step,
    make_claude_code_coder_step,
    reset_claude_run_costs,
)


@dataclass(frozen=True)
class ClassSpec:
    """Single-class TDD target — module, package, class derived from `**Module/Package/Class:**` headers."""
    module: str        # gradle reference, e.g. ":feature:favorites"
    package: str       # e.g. "com.aj.giphysearch.feature.favorites.ui"
    class_name: str    # e.g. "FavoritesViewModel"

    @property
    def module_path(self) -> str:
        return self.module.lstrip(":").replace(":", "/")

    @property
    def package_path(self) -> str:
        return self.package.replace(".", "/")

    @property
    def test_file_path(self) -> str:
        return f"{self.module_path}/src/test/kotlin/{self.package_path}/{self.class_name}Test.kt"

    @property
    def impl_file_path(self) -> str:
        return f"{self.module_path}/src/main/kotlin/{self.package_path}/{self.class_name}.kt"


_FIELD_RE = re.compile(r"\*\*([A-Za-z]+):\*\*\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)
_SMELTERS_HEADER_RE = re.compile(r"^Project:\s*\S+", re.MULTILINE)


def detect_format(text: str) -> str:
    """class → has **Module/Package/Class:**; smelters → starts with `Project: <name>`; unknown otherwise."""
    if _FIELD_RE.search(text):
        fields = {m.group(1) for m in _FIELD_RE.finditer(text)}
        if {"Module", "Package", "Class"}.issubset(fields):
            return "class"
    if _SMELTERS_HEADER_RE.search(text):
        return "smelters"
    return "unknown"


def parse_class_spec(text: str, source: Path) -> ClassSpec:
    fields: Dict[str, str] = {m.group(1): m.group(2).strip() for m in _FIELD_RE.finditer(text)}
    missing = [k for k in ("Module", "Package", "Class") if k not in fields]
    if missing:
        sys.exit(
            f"ERROR: {source} is missing required field(s): {', '.join('**' + m + ':**' for m in missing)}\n"
            "Add lines like these near the top of the task file:\n"
            "    **Module:** `:feature:favorites`\n"
            "    **Package:** `com.aj.giphysearch.feature.favorites.ui`\n"
            "    **Class:** `FavoritesViewModel`\n"
        )
    module = fields["Module"]
    if not module.startswith(":"):
        module = f":{module}"
    return ClassSpec(module=module, package=fields["Package"], class_name=fields["Class"])


def derive_project_path(task_path: Path) -> Path:
    """tasks/DemoApp/6-foo.md → projects/DemoApp"""
    parts = task_path.parts
    if "tasks" not in parts:
        sys.exit(
            f"ERROR: cannot derive project path from {task_path}\n"
            "Either place the task under tasks/<ProjectName>/... or pass --project explicitly."
        )
    idx = parts.index("tasks")
    if idx + 1 >= len(parts) - 1:
        sys.exit(
            f"ERROR: task at {task_path} is not nested under tasks/<ProjectName>/. "
            "Pass --project explicitly."
        )
    project_name = parts[idx + 1]
    return Path("projects") / project_name


def lint_state_saver(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> StepOutput:
    content = step_input.previous_step_content or ""
    if session_state is not None:
        session_state["lint_result"] = content
    return StepOutput(content=content)


def test_state_saver(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> StepOutput:
    content = step_input.previous_step_content or ""
    if session_state is not None:
        session_state["test_result"] = content
    return StepOutput(content=content)


def _lint_failed(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> bool:
    state = session_state or {}
    return not (state.get("lint_result") or "").startswith("LINT_OK")


def _tests_failed(step_input: StepInput, session_state: Optional[Dict[str, Any]] = None) -> bool:
    state = session_state or {}
    return not (state.get("test_result") or "").startswith("TESTS_OK")


def build_workflow(task_dir: str, project_path: str, spec: ClassSpec, auto: bool = False) -> Workflow:
    test_case_agent = make_test_case_agent(
        task_path=task_dir,
        package=spec.package,
        class_name=spec.class_name,
    )
    test_writer_agent = make_test_writer_agent(
        project_path=project_path,
        package=spec.package,
        class_name=spec.class_name,
        test_file_path=spec.test_file_path,
    )
    impl_agent = make_impl_agent(
        project_path=project_path,
        package=spec.package,
        class_name=spec.class_name,
        impl_file_path=spec.impl_file_path,
        test_file_path=spec.test_file_path,
    )
    lint_fix_agent = make_lint_fix_agent(project_path=project_path, module=spec.module)
    test_run_agent = make_test_run_agent(
        project_path=project_path,
        module=spec.module,
        impl_file_path=spec.impl_file_path,
    )

    lint_loop = Loop(
        name="LintLoop",
        steps=[lint_fix_agent],
        max_iterations=3,
        end_condition=lambda outputs: bool(outputs) and (outputs[-1].content or "").startswith("LINT_OK"),
        forward_iteration_output=True,
    )

    test_loop = Loop(
        name="TestLoop",
        steps=[test_run_agent],
        max_iterations=3,
        end_condition=lambda outputs: bool(outputs) and (outputs[-1].content or "").startswith("TESTS_OK"),
        forward_iteration_output=True,
    )

    steps: list = [test_case_agent, test_writer_agent, impl_agent, lint_loop, lint_state_saver]

    if not auto:
        lint_fix_agent_gate = make_lint_fix_agent(project_path=project_path, module=spec.module)
        lint_human_review_step = Step(
            agent=lint_fix_agent_gate,
            human_review=HumanReview(
                requires_confirmation=True,
                confirmation_message=(
                    f"⚠️  detekt failed for {spec.module} after 3 attempts. "
                    "Please fix detekt errors manually, then confirm to continue."
                ),
                on_reject=OnReject.cancel,
            ),
        )
        steps.append(Condition(steps=[lint_human_review_step], evaluator=_lint_failed))

    steps.append(test_loop)
    steps.append(test_state_saver)

    if not auto:
        test_run_agent_gate = make_test_run_agent(
            project_path=project_path,
            module=spec.module,
            impl_file_path=spec.impl_file_path,
        )
        test_human_review_step = Step(
            agent=test_run_agent_gate,
            human_review=HumanReview(
                requires_confirmation=True,
                confirmation_message=(
                    f"⚠️  Tests failed for {spec.module} after 3 attempts. "
                    "Please fix the implementation manually, then confirm to continue."
                ),
                on_reject=OnReject.cancel,
            ),
        )
        steps.append(Condition(steps=[test_human_review_step], evaluator=_tests_failed))

    return Workflow(name="AgnoTDDWorkflow", steps=steps, db=_ephemeral_db())


def _fmt_int(n: int) -> str:
    """1234 -> '1 234'"""
    return f"{n:,}".replace(",", " ")


def _fmt_seconds(secs: float) -> str:
    if secs < 60:
        return f"{secs:.1f}s"
    m, s = divmod(int(secs), 60)
    return f"{m}m {s}s"


_CHECKER_JSON_RE = re.compile(r'\{[^{}]*"status"\s*:\s*"(passed|failed)"[^{}]*\}')


def _scan_checker_status(content: Optional[str]) -> Optional[str]:
    """Find the LAST checker JSON in arbitrary content and return its `status`."""
    if not content:
        return None
    last: Optional[str] = None
    for m in _CHECKER_JSON_RE.finditer(content):
        last = m.group(1)
    return last


def _is_transient(exc: BaseException) -> bool:
    """Treat network blips, rate limits, and 5xx as retryable. Everything else surfaces."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    transient_markers = (
        "rate limit", "rate_limit", "ratelimit", "429",
        "502", "503", "504", "overloaded", "timeout",
        "connection", "temporarily unavailable", "service unavailable",
        "resource_exhausted", "deadline_exceeded", "unavailable",
    )
    if any(m in msg for m in transient_markers):
        return True
    if "timeout" in name or "connection" in name or "apierror" in name:
        return True
    return False


def run_with_metrics(
    workflow: Workflow,
    prompt: str,
    stream: bool = True,
    *,
    session_id: Optional[str] = None,
    task_id: Optional[int] = None,
    events_path: Optional[Path] = None,
    max_iterations: Optional[int] = None,
) -> None:
    """Run the workflow with a live rich progress display, then print a metrics summary.

    When `task_id` and `events_path` are provided, also emits structured events to
    events.jsonl: `loop_iteration`, `task_aborted`, `agent_error_caught`. On transient
    LLM API errors the run is retried with the same `session_id`, letting Agno's
    persistent storage resume from the last cached step result."""
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table

    if session_id is None:
        session_id = str(uuid.uuid4())
    reset_claude_run_costs()
    start = time.time()

    emit_to_jsonl = task_id is not None and events_path is not None

    def _emit(actor: str, type_: str, **fields: Any) -> None:
        if emit_to_jsonl:
            try:
                emit_event(events_path, task_id=task_id, actor=actor, type=type_, **fields)
            except Exception:  # noqa: BLE001 — never let telemetry break the run
                pass

    state: Dict[str, Any] = {
        "steps": [],
        "loop": None,
        "iterations_started": 0,
        "iterations_completed": 0,
        "last_checker_status": None,
    }

    STATUS_ICON = {
        "waiting": "[dim]○[/dim]",
        "running": "[bold yellow]⟳[/bold yellow]",
        "done":    "[bold green]✓[/bold green]",
        "failed":  "[bold red]✗[/bold red]",
    }

    def _step(name: Optional[str]) -> Optional[Dict[str, Any]]:
        return next((s for s in state["steps"] if s["name"] == name), None)

    def _make_panel() -> Panel:
        elapsed = time.time() - start
        tbl = Table.grid(padding=(0, 1))
        tbl.add_column(width=2)
        tbl.add_column(min_width=28)
        tbl.add_column(style="dim", min_width=8)

        for s in state["steps"]:
            icon = STATUS_ICON.get(s["status"], "?")
            dur = ""
            if s["status"] == "running":
                dur = _fmt_seconds(time.time() - s["t0"])
                label = f"[bold]{s['name']}[/bold]"
            elif s["status"] == "done":
                dur = _fmt_seconds(s["t1"] - s["t0"])
                label = s["name"] or ""
            elif s["status"] == "failed":
                label = f"[red]{s['name']}[/red]"
                dur = "failed"
            else:
                label = f"[dim]{s['name']}[/dim]"
            tbl.add_row(icon, label, dur)

        lp = state["loop"]
        loop_line = (
            f"  [dim]{lp['name']}[/dim]  iter {lp['iter']}/{lp['max'] or '?'}"
            if lp else ""
        )
        subtitle = f"[dim]{_fmt_seconds(elapsed)}[/dim]{loop_line}"
        return Panel(tbl, title=f"[bold blue]{workflow.name}[/bold blue]", subtitle=subtitle, border_style="blue")

    console = Console(stderr=True)

    def _consume_events(live: "Live") -> None:
        event_iter = workflow.run(
            input=prompt,
            session_id=session_id,
            stream=True,
            stream_events=True,
        )
        for event in event_iter:
            evt = getattr(event, "event", "")
            name = getattr(event, "step_name", None)

            if evt == "StepStarted":
                existing = _step(name)
                if existing:
                    existing["status"] = "running"
                    existing["t0"] = time.time()
                else:
                    state["steps"].append({"name": name, "status": "running", "t0": time.time(), "t1": 0.0})

            elif evt == "StepCompleted":
                s = _step(name)
                if s:
                    s["status"] = "done"
                    s["t1"] = time.time()
                status = _scan_checker_status(getattr(event, "content", None))
                if status:
                    state["last_checker_status"] = status

            elif evt == "StepError":
                s = _step(name)
                if s:
                    s["status"] = "failed"
                    s["t1"] = time.time()

            elif evt == "LoopIterationStarted":
                iter_num = getattr(event, "iteration", 0) + 1
                max_iters = getattr(event, "max_iterations", max_iterations)
                state["loop"] = {
                    "name": name or "Loop",
                    "iter": iter_num,
                    "max": max_iters,
                }
                state["iterations_started"] = max(state["iterations_started"], iter_num)
                _emit(
                    actor="orchestrator",
                    type_="loop_iteration",
                    iteration=iter_num,
                    max=max_iters if max_iters is not None else max_iterations,
                )

            elif evt == "LoopIterationCompleted":
                iter_num = getattr(event, "iteration", 0) + 1
                state["iterations_completed"] = max(state["iterations_completed"], iter_num)
                if state["loop"]:
                    state["loop"]["iter"] = iter_num

            elif evt in ("LoopExecutionCompleted", "WorkflowCompleted"):
                state["loop"] = None

            live.update(_make_panel())

    try:
        with Live(_make_panel(), console=console, refresh_per_second=4) as live:
            attempt = 0
            while True:
                try:
                    _consume_events(live)
                    break
                except Exception as exc:  # noqa: BLE001
                    attempt += 1
                    _emit(
                        actor="orchestrator",
                        type_="agent_error_caught",
                        error=f"{type(exc).__name__}: {exc}",
                        attempt=attempt,
                    )
                    if attempt >= RETRY_MAX_ATTEMPTS or not _is_transient(exc):
                        print(
                            f"[agno_orchestrator] giving up after {attempt} attempt(s): {type(exc).__name__}: {exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                        raise
                    delay = RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                    print(
                        f"[agno_orchestrator] transient error (attempt {attempt}/{RETRY_MAX_ATTEMPTS}): "
                        f"{type(exc).__name__}: {exc} — retrying in {delay:.1f}s",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(delay)

        if (
            state["last_checker_status"] != "passed"
            and max_iterations is not None
            and state["iterations_started"] >= max_iterations
        ):
            _emit(
                actor="orchestrator",
                type_="task_aborted",
                reason="MAX_FIX_ITERATIONS_REACHED",
                iterations=state["iterations_started"],
                max=max_iterations,
            )

    finally:
        elapsed = time.time() - start
        try:
            metrics = workflow.get_session_metrics(session_id=session_id)
        except Exception as exc:  # noqa: BLE001
            metrics = None
            metrics_err = str(exc)
        else:
            metrics_err = None
        claude_costs = get_claude_run_costs()  # [(label, usd), ...] from claude-cli steps

        print()
        print("┏━ Run Summary " + "━" * 60)
        print(f"┃  Wall-clock time:    {_fmt_seconds(elapsed)}")

        # Agno-tracked agents (Claude/Gemini via API)
        if metrics is None:
            if not claude_costs:
                print(f"┃  Token metrics:      unavailable ({metrics_err})")
        else:
            total_in = metrics.input_tokens or 0
            total_out = metrics.output_tokens or 0
            total = metrics.total_tokens or (total_in + total_out)
            cache_r = metrics.cache_read_tokens or 0
            cache_w = metrics.cache_write_tokens or 0
            reasoning = metrics.reasoning_tokens or 0
            if total or claude_costs:
                print(f"┃  [Agno-tracked agents (API)]")
                print(f"┃    Tokens — input:   {_fmt_int(total_in)}")
                print(f"┃    Tokens — output:  {_fmt_int(total_out)}")
                if reasoning:
                    print(f"┃    Tokens — reason: {_fmt_int(reasoning)}")
                if cache_r or cache_w:
                    print(f"┃    Tokens — cache:  read {_fmt_int(cache_r)}, write {_fmt_int(cache_w)}")
                print(f"┃    Tokens — total:  {_fmt_int(total)}")
                if metrics.cost is not None:
                    print(f"┃    Cost (USD):     ${metrics.cost:.4f}")
                if metrics.details:
                    for model_id, model_metrics_list in metrics.details.items():
                        in_sum = sum((m.input_tokens or 0) for m in model_metrics_list)
                        out_sum = sum((m.output_tokens or 0) for m in model_metrics_list)
                        calls = len(model_metrics_list)
                        print(f"┃    {model_id}: {calls} calls, in={_fmt_int(in_sum)}, out={_fmt_int(out_sum)}")

        # claude-cli (subprocess) — costs reported by claude itself in the result event
        if claude_costs:
            total_cli_cost = sum(c for _, c in claude_costs)
            print(f"┃  [claude-cli (subscription)]")
            for label, cost in claude_costs:
                print(f"┃    {label}: ${cost:.4f}")
            print(f"┃    Total cost:     ${total_cli_cost:.4f} ({len(claude_costs)} call(s))")
        print("┗" + "━" * 73)


def _parse_checker_status(content: str) -> str:
    """Extract `status` from CodeChecker's last-line JSON. Returns 'passed', 'failed', or 'unknown'."""
    if not content:
        return "unknown"
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") and "status" in line and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except (ValueError, TypeError):
                continue
            return parsed.get("status", "unknown") if isinstance(parsed, dict) else "unknown"
    return "unknown"


def _checker_passed(outputs: List[Any]) -> bool:
    if not outputs:
        return False
    return _parse_checker_status(outputs[-1].content or "") == "passed"


_MAX_DIFF_CHARS = 8000


def _git(project: Path, *args: str, timeout: int = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(project), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, ""
    return proc.returncode, proc.stdout


def make_diff_tracker(project_path: str) -> Callable[..., StepOutput]:
    """Step injected after the checker. Snapshots the worktree via `git stash create`
    each iteration; on the *next* iteration prepends the textual diff between the
    previous snapshot and the current worktree to the checker JSON, so the coder sees
    exactly what its prior attempt changed and avoids reverting useful edits.
    The checker JSON stays the LAST line, so `_checker_passed` keeps working."""
    project = Path(project_path).resolve()

    def diff_tracker(
        step_input: StepInput,
        session_state: Optional[Dict[str, Any]] = None,
    ) -> StepOutput:
        state = session_state if session_state is not None else {}
        prev_sha = state.get("diff_baseline_sha")

        prev_diff_text = ""
        if prev_sha:
            rc, out = _git(project, "diff", "--no-color", prev_sha)
            if rc == 0:
                prev_diff_text = out

        rc, sha = _git(project, "stash", "create")
        new_sha = sha.strip()
        if rc == 0 and new_sha:
            state["diff_baseline_sha"] = new_sha

        checker_content = step_input.previous_step_content or ""
        if not prev_diff_text.strip():
            return StepOutput(content=checker_content)

        truncated = (
            prev_diff_text
            if len(prev_diff_text) <= _MAX_DIFF_CHARS
            else prev_diff_text[:_MAX_DIFF_CHARS] + "\n...(diff truncated)...\n"
        )
        combined = (
            "PREVIOUS_ITERATION_DIFF (changes your previous attempt made — review them; "
            "do NOT blindly revert correct edits while addressing the checker report):\n"
            "```diff\n" + truncated + "\n```\n\n"
            "CHECKER_REPORT:\n" + checker_content
        )
        return StepOutput(content=combined)

    return diff_tracker


def build_smelters_workflow(
    project_path: str,
    task_content: str,
    coder_model: str = "claude",
    checker_backend: str = "gemini",
    max_iterations: int = MAX_FIX_ITERATIONS,
    coder_claude_model: str = "sonnet",
    checker_claude_model: str = "sonnet",
    db: Optional[SqliteDb] = None,
) -> Workflow:
    """Two-step loop: coder writes tests + impl + RUN_TESTS.sh; checker runs the script.
    On failure the checker's JSON becomes input to the next coder iteration.

    Args:
        coder_model: coder backend:
          - "claude":     Agno Agent on Claude Sonnet 4.6 (needs ANTHROPIC_API_KEY)
          - "gemini":     Agno Agent on Gemini 3.1 Pro Preview (needs GOOGLE_API_KEY)
          - "claude-cli": subprocess to `claude -p` (needs Claude Code logged in)
        checker_backend: checker backend:
          - "gemini":     Agno Agent on Gemini 3.1 Pro Preview (needs GOOGLE_API_KEY)
          - "claude-cli": subprocess to `claude -p` (needs Claude Code logged in)
        coder_claude_model: model passed to `claude --model ...` when
            coder_model == 'claude-cli'. Aliases ("sonnet" [default], "opus", "haiku")
            or full IDs ("claude-sonnet-4-6"). Ignored for other backends.
        checker_claude_model: same as above but for checker (default "sonnet"; "haiku"
            is a great cheap pick for the checker phase).
    """
    if coder_model == "claude-cli":
        coder_step = make_claude_code_coder_step(
            project_path=project_path,
            task_content=task_content,
            model_alias=coder_claude_model,
        )
    else:
        coder_step = make_android_coder(
            project_path=project_path,
            task_content=task_content,
            model=coder_model,
        )

    if checker_backend == "claude-cli":
        checker_step = make_claude_code_checker_step(
            project_path=project_path,
            model_alias=checker_claude_model,
        )
    else:
        checker_step = make_code_checker(project_path=project_path)

    diff_step = make_diff_tracker(project_path=project_path)

    coder_checker_loop = Loop(
        name="CoderCheckerLoop",
        steps=[coder_step, checker_step, diff_step],
        max_iterations=max_iterations,
        end_condition=_checker_passed,
        forward_iteration_output=True,
    )

    return Workflow(
        name="AgnoWorkflow",
        steps=[coder_checker_loop],
        db=db if db is not None else _ephemeral_db(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orchestrator. Two pipelines: class-mode TDD (single Kotlin class) and smelters-mode (open-ended PRD).",
        epilog=(
            "Layout:\n"
            "    tasks/<Project>/<N>-<slug>.md   ← task spec\n"
            "    projects/<Project>/             ← target Gradle codebase\n"
            "\n"
            "Smelters mode (open-ended PRD) — task starts with `Project: <Name>`:\n"
            "    Loop x N: AndroidCoder writes tests + impl + RUN_TESTS.sh\n"
            "                  ⇣\n"
            "              CodeChecker runs RUN_TESTS.sh, parses TEST-*.xml\n"
            "                  ⇣ (if failed → JSON feedback to coder, retry)\n"
            "              done when status==passed or max iterations reached\n"
            "    Default coder: Claude Sonnet 4.6 (use --coder gemini for cheap fallback).\n"
            "\n"
            "Class mode (single-class TDD) — task has `**Module/Package/Class:**` headers:\n"
            "    TestCase → TestWriter → Impl → LintLoop(detekt) → TestLoop(:module:test)\n"
            "    Coder/checker on Gemini 2.5 Flash. --auto disables human-review gates."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Path to task .md file (e.g. tasks/DemoApp/6-favorites-bookmarks-system.md)",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Path to target Gradle root. Default: auto-detected as projects/<Name> from --task path.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help=(
            "Run unattended — drop human-review gates (class mode only). "
            "If LintLoop or TestLoop hits its 3-iteration cap, the orchestrator finishes anyway "
            "(read the log to see whether LINT_OK / TESTS_OK was actually reached)."
        ),
    )
    parser.add_argument(
        "--coder",
        choices=("claude", "gemini", "claude-cli"),
        default="claude-cli",
        help=(
            "Coder backend in smelters mode. "
            "'claude-cli' = subprocess to `claude -p` (default, uses Claude Code's subscription/auth and bundled tools). "
            "'claude' = Agno+Sonnet 4.6 (needs ANTHROPIC_API_KEY). "
            "'gemini' = Agno+Gemini 3.1 Pro Preview (needs GOOGLE_API_KEY)."
        ),
    )
    parser.add_argument(
        "--checker",
        choices=("gemini", "claude-cli"),
        default="claude-cli",
        help=(
            "Checker backend in smelters mode. "
            "'claude-cli' = subprocess to `claude -p` (default, uses Claude Code's auth, no Google key needed). "
            "'gemini' = Agno+Gemini 3.1 Pro Preview (needs GOOGLE_API_KEY)."
        ),
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=MAX_FIX_ITERATIONS,
        help=f"Max iterations of the coder ⇄ checker loop (smelters mode). Default: {MAX_FIX_ITERATIONS}.",
    )
    parser.add_argument(
        "--coder-model",
        default="sonnet",
        help=(
            "Model for the coder when --coder claude-cli. "
            "Aliases ('sonnet' [default], 'opus', 'haiku' → latest of each family) "
            "or full IDs ('claude-sonnet-4-6', 'claude-opus-4-7'). "
            "Ignored for --coder claude/gemini."
        ),
    )
    parser.add_argument(
        "--checker-model",
        default="sonnet",
        help=(
            "Model for the checker when --checker claude-cli. "
            "Aliases ('sonnet' [default], 'opus', 'haiku') or full IDs. "
            "'haiku' is a fine cheap pick — checker just runs a script and parses XML. "
            "Ignored for --checker gemini."
        ),
    )
    parser.add_argument(
        "--task-id",
        type=int,
        default=None,
        help=(
            "Tracker task ID (smelters mode). When set, structured events "
            "(loop_iteration, task_aborted, agent_error_caught) are emitted to events.jsonl "
            "and the Agno session is persisted at database/<Project>/agno-session.sqlite, "
            "enabling resume-where-it-left-off if the run crashes."
        ),
    )
    parser.add_argument(
        "--events-path",
        type=Path,
        default=None,
        help=(
            "Path to events.jsonl (smelters mode, paired with --task-id). "
            "Defaults to $EVENTS_PATH or database/<Project>/events.jsonl."
        ),
    )
    args = parser.parse_args()

    task_path = Path(args.task)
    if not task_path.exists() or not task_path.is_file():
        sys.exit(f"ERROR: task file not found: {task_path}")

    text = task_path.read_text()
    fmt = detect_format(text)

    if fmt == "unknown":
        sys.exit(
            f"ERROR: cannot detect task format in {task_path}.\n"
            "Expected one of:\n"
            "  • smelters: first line `Project: <Name>` (open-ended PRD)\n"
            "  • class:    headers `**Module:**`, `**Package:**`, `**Class:**` (single-class TDD)\n"
        )

    project_path = Path(args.project) if args.project else derive_project_path(task_path)
    if not project_path.exists():
        sys.exit(f"ERROR: project not found at {project_path}")

    if fmt == "smelters":
        if args.coder == "claude" and not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit(
                "ERROR: ANTHROPIC_API_KEY is not set (required for --coder claude / default).\n"
                "  Set it, or pass --coder gemini / --coder claude-cli."
            )
        needs_claude_cli = args.coder == "claude-cli" or args.checker == "claude-cli"
        if needs_claude_cli:
            from shutil import which
            if not (which("claude") or os.environ.get("CLAUDE_BIN")):
                sys.exit(
                    "ERROR: claude CLI not found on PATH (required for any --coder/--checker claude-cli).\n"
                    "  Install Claude Code or set $CLAUDE_BIN to the binary path."
                )
        needs_google = args.coder == "gemini" or args.checker == "gemini"
        if needs_google and not os.environ.get("GOOGLE_API_KEY"):
            sys.exit(
                "ERROR: GOOGLE_API_KEY is not set (required for any --coder/--checker gemini).\n"
                "  Get a key at https://aistudio.google.com/app/apikey, then export GOOGLE_API_KEY=…\n"
                "  Or pass --coder claude-cli --checker claude-cli to skip Google entirely."
            )

        coder_label = {
            "claude": "Claude Sonnet 4.6 (Agno API)",
            "gemini": "Gemini 3.1 Pro (preview, custom-tools)",
            "claude-cli": f"Claude Code CLI (`claude -p --model {args.coder_model}`, subscription auth)",
        }[args.coder]
        checker_label = {
            "gemini": "Gemini 3.1 Pro (preview, custom-tools)",
            "claude-cli": f"Claude Code CLI (`claude -p --model {args.checker_model}`, subscription auth)",
        }[args.checker]
        print(
            "[AgnoWorkflow]\n"
            f"  Task:    {task_path}\n"
            f"  Project: {project_path}\n"
            f"  Coder:   {coder_label}\n"
            f"  Checker: {checker_label}\n"
            f"  Loop:    Coder ⇄ Checker, max {args.max_iterations} iterations\n"
        )

        events_path: Optional[Path] = args.events_path
        if events_path is None and os.environ.get("EVENTS_PATH"):
            events_path = Path(os.environ["EVENTS_PATH"])

        persistent_db: Optional[SqliteDb] = None
        smelters_session_id: Optional[str] = None
        if args.task_id is not None:
            project_name = project_path.name
            db_dir = Path("database") / project_name
            db_dir.mkdir(parents=True, exist_ok=True)
            persistent_db = SqliteDb(db_file=str(db_dir / "agno-session.sqlite"))
            smelters_session_id = f"task-{args.task_id}"
            if events_path is None:
                events_path = db_dir / "events.jsonl"
            events_path.parent.mkdir(parents=True, exist_ok=True)
            print(
                f"  Session: {smelters_session_id} (persistent at {db_dir / 'agno-session.sqlite'})\n"
                f"  Events:  {events_path}\n"
            )

        workflow = build_smelters_workflow(
            project_path=str(project_path),
            task_content=text,
            coder_model=args.coder,
            checker_backend=args.checker,
            max_iterations=args.max_iterations,
            coder_claude_model=args.coder_model,
            checker_claude_model=args.checker_model,
            db=persistent_db,
        )
        run_with_metrics(
            workflow,
            "Begin work on the task spec embedded in your instructions.",
            session_id=smelters_session_id,
            task_id=args.task_id,
            events_path=events_path,
            max_iterations=args.max_iterations,
        )
        sys.exit(0)

    # fmt == "class"
    if not os.environ.get("GOOGLE_API_KEY"):
        sys.exit(
            "ERROR: GOOGLE_API_KEY is not set (required for class-mode TDD pipeline).\n"
            "  Get a key at https://aistudio.google.com/app/apikey, then export GOOGLE_API_KEY=…"
        )

    spec = parse_class_spec(text, task_path)
    print(
        "[AgnoTDDWorkflow]\n"
        f"  Task:    {task_path}\n"
        f"  Project: {project_path}\n"
        f"  Module:  {spec.module}\n"
        f"  Package: {spec.package}\n"
        f"  Class:   {spec.class_name}\n"
        f"  Test:    {spec.test_file_path}\n"
        f"  Impl:    {spec.impl_file_path}\n"
        f"  Mode:    {'AUTO (no human gates)' if args.auto else 'INTERACTIVE (human gates on failure)'}\n"
    )

    workflow = build_workflow(
        task_dir=str(task_path.parent),
        project_path=str(project_path),
        spec=spec,
        auto=args.auto,
    )
    prompt = (
        f"Implement {spec.package}.{spec.class_name} in module {spec.module}. "
        f"Spec: {task_path}. Project root: {project_path}."
    )
    run_with_metrics(workflow, prompt)


if __name__ == "__main__":
    main()
