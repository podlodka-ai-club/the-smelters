# Project-First Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the orchestration runtime fully project-scoped, with mandatory `--project`, project-local databases/events/worktrees, and project-local task numbers.

**Architecture:** Introduce project-path resolution helpers and a project-local tracker schema keyed by `task_number`. Then update seeding, orchestrator, agents, printer, and TUI to derive all runtime state from `--project`, followed by test and README updates. Shared orchestration code remains top-level while project-specific fixtures move under `tests/<project>/`.

**Tech Stack:** Python, SQLite, Textual, pytest

---

### Task 1: Add project runtime path helpers

**Files:**
- Create: `src/runtime_paths.py`
- Test: `tests/test_runtime_paths.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from src.runtime_paths import project_runtime_paths


def test_project_runtime_paths_resolve_all_locations(tmp_path: Path) -> None:
    paths = project_runtime_paths(tmp_path, "DemoApp")

    assert paths.project == "DemoApp"
    assert paths.repo_path == tmp_path / "projects" / "DemoApp"
    assert paths.tasks_path == tmp_path / "tasks" / "DemoApp"
    assert paths.db_path == tmp_path / "database" / "DemoApp" / "tasks.db"
    assert paths.events_path == tmp_path / "database" / "DemoApp" / "events.jsonl"
    assert paths.worktrees_path == tmp_path / "worktrees" / "DemoApp"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runtime_paths.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing helper.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True, slots=True)
class ProjectRuntimePaths:
    project: str
    repo_path: Path
    tasks_path: Path
    db_path: Path
    events_path: Path
    worktrees_path: Path


def project_runtime_paths(root: Path, project: str) -> ProjectRuntimePaths:
    return ProjectRuntimePaths(
        project=project,
        repo_path=root / "projects" / project,
        tasks_path=root / "tasks" / project,
        db_path=root / "database" / project / "tasks.db",
        events_path=root / "database" / project / "events.jsonl",
        worktrees_path=root / "worktrees" / project,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_runtime_paths.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_runtime_paths.py src/runtime_paths.py
git commit -m "refactor: add project runtime path helpers"
```

### Task 2: Move tracker and model to project-local task numbers

**Files:**
- Modify: `src/models.py`
- Modify: `src/tracker.py`
- Modify: `tests/test_models.py`
- Modify: `tests/test_tracker.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_insert_and_get_uses_task_number(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    row_id = tracker.insert_task(task_number=7, title="demo", spec_path="tasks/DemoApp/7-demo.md")
    task = tracker.get_task(row_id)
    assert task.task_number == 7


def test_claim_next_ready_orders_by_task_number(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    tracker.insert_task(task_number=9, title="later", spec_path="tasks/DemoApp/9-later.md")
    tracker.insert_task(task_number=2, title="earlier", spec_path="tasks/DemoApp/2-earlier.md")
    claimed = tracker.claim_next_ready_task()
    assert claimed is not None
    assert claimed.task_number == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py tests/test_tracker.py -q`
Expected: FAIL because `task_number` is absent and inserts still require `project`.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(slots=True)
class Task:
    id: int
    task_number: int
    title: str
    spec_path: str
    status: Status
    attempts: int
    worktree: str | None
    branch: str | None
    review_notes: str | None
```

```python
CREATE TABLE IF NOT EXISTS tasks (
  id           INTEGER PRIMARY KEY,
  task_number  INTEGER NOT NULL UNIQUE,
  title        TEXT NOT NULL,
  spec_path    TEXT NOT NULL,
  status       TEXT NOT NULL,
  attempts     INTEGER NOT NULL DEFAULT 0,
  worktree     TEXT,
  branch       TEXT,
  review_notes TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py tests/test_tracker.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py src/tracker.py tests/test_models.py tests/test_tracker.py
git commit -m "refactor: make tracker project local"
```

### Task 3: Update seeding to require project and parse task numbers

**Files:**
- Modify: `seed.py`
- Modify: `tests/test_project_profile.py`
- Create: `tests/test_seed.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_seed_requires_project_argument() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_seed_reads_only_selected_project(tmp_path: Path, tmp_db: Path) -> None:
    tasks_root = tmp_path / "tasks"
    demo_tasks = tasks_root / "DemoApp"
    demo_tasks.mkdir(parents=True)
    (demo_tasks / "7-share.md").write_text("Project: DemoApp\n\n# Share\n", encoding="utf-8")
    projects_root = tmp_path / "projects"
    (projects_root / "DemoApp").mkdir(parents=True)
    seed(tmp_db, project="DemoApp", tasks_root=tasks_root, projects_root=projects_root)
    rows = list(Tracker(tmp_db).list_tasks())
    assert [row.task_number for row in rows] == [7]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_seed.py tests/test_project_profile.py -q`
Expected: FAIL because `seed` does not take `project` and does not parse task numbers.

- [ ] **Step 3: Write minimal implementation**

```python
def _task_number_from_filename(path: Path) -> int:
    match = re.match(r"^(\\d+)[-_]", path.name)
    if not match:
        raise AssertionError(f"task filename must start with an integer prefix: {path.name}")
    return int(match.group(1))
```

```python
def seed(db_path: Path, *, project: str, tasks_root: Path, projects_root: Path) -> None:
    project_tasks = tasks_root / project
    project_repo = projects_root / project
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_seed.py tests/test_project_profile.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add seed.py tests/test_seed.py tests/test_project_profile.py
git commit -m "refactor: seed project-local task databases"
```

### Task 4: Make orchestrator project-scoped and task-number aware

**Files:**
- Modify: `orchestrator.py`
- Modify: `agents/runner.py`
- Modify: `agents/coder.py`
- Modify: `agents/reviewer.py`
- Modify: `tests/test_orchestrator.py`
- Modify: `tests/test_coder.py`
- Modify: `tests/test_reviewer.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_main_requires_project() -> None:
    with pytest.raises(SystemExit):
        main([])


@pytest.mark.asyncio
async def test_task_filter_uses_task_number(tmp_path: Path, tmp_db: Path, tmp_events: Path, monkeypatch) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    tracker.insert_task(task_number=7, title="demo", spec_path="tasks/DemoApp/7-demo.md")
    orch = Orchestrator(..., task_filter=7)
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_orchestrator.py tests/test_coder.py tests/test_reviewer.py -q`
Expected: FAIL because runtime commands do not require `--project` and agent invocation still uses row id semantics.

- [ ] **Step 3: Write minimal implementation**

```python
cmd = [sys.executable, "-m", f"agents.{role}", str(task.id)]
```

Keep the internal row id for subprocess handoff, but update prompts and event handling to display `task.task_number` in user-facing text. Derive DB, events, tasks, and worktree paths from `--project`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_orchestrator.py tests/test_coder.py tests/test_reviewer.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add orchestrator.py agents/runner.py agents/coder.py agents/reviewer.py tests/test_orchestrator.py tests/test_coder.py tests/test_reviewer.py
git commit -m "refactor: scope orchestrator runtime to one project"
```

### Task 5: Update printer and TUI for project-local runtime

**Files:**
- Modify: `printer.py`
- Modify: `tui.py`
- Create: `tests/test_tui.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_dashboard_loads_task_numbers(tmp_db: Path) -> None:
    tracker = Tracker(tmp_db)
    tracker.init_schema()
    tracker.insert_task(task_number=3, title="demo", spec_path="tasks/DemoApp/3-demo.md")
    rows = load_task_rows(tmp_db)
    assert rows == [("3", "ready", "0", "demo")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tui.py -q`
Expected: FAIL because TUI still selects and shows row ids.

- [ ] **Step 3: Write minimal implementation**

```python
table.add_columns("task", "status", "attempts", "title")
rows = conn.execute("SELECT task_number, status, attempts, title FROM tasks ORDER BY task_number")
```

Require `--project` and derive `db_path` / `events_path` from project runtime paths.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tui.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add printer.py tui.py tests/test_tui.py
git commit -m "refactor: scope dashboard and printer to one project"
```

### Task 6: Reorganize project-specific tests and refresh docs

**Files:**
- Move: `tests/test_python_fixture_integration.py` -> `tests/python_fixture/test_integration.py`
- Move: `tests/test_e2e_smoke.py` -> `tests/python_fixture/test_e2e_smoke.py`
- Modify: `README.md`

- [ ] **Step 1: Write or update failing tests/imports**

```python
def test_python_fixture_paths_match_project_layout(...):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/python_fixture -q`
Expected: FAIL until moved imports and paths are corrected.

- [ ] **Step 3: Write minimal implementation**

Move the files, update any repo-relative path assumptions, and document:

```bash
.venv/bin/python seed.py --project python_fixture
.venv/bin/python orchestrator.py --project python_fixture --task 1 --watch
.venv/bin/python printer.py --project python_fixture
.venv/bin/python tui.py --project python_fixture
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/python_fixture -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/python_fixture README.md
git commit -m "docs: document project-first runtime commands"
```

### Task 7: Run full verification

**Files:**
- Modify: none expected

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all non-live tests pass

- [ ] **Step 2: Review git diff**

Run: `git diff --stat`
Expected: only project-first runtime files and test/doc updates are present

- [ ] **Step 3: Commit any final fixes**

```bash
git add -A
git commit -m "refactor: complete project-first runtime migration"
```
