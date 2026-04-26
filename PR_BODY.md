# feat/build-verification — Android coder, worktrees, and opencode

## Summary

Hardens the Android coding agent around **opencode** (with health checks, streaming, heartbeats, inactivity timeout, and recovery), routes **all edits through task sandboxes** under `worktrees/<project>/task-<N>` (never the canonical `projects/<project>` tree), aligns **`run_android_coder.sh`** with the orchestrator, and moves agent settings to **`agent_config.yml`** (drops `agent_config.json`).

## Why

- Previously, `run_android_coder.sh` could `cd` into `projects/DemoApp`, so the agent wrote to the template tree while SQLite pointed at `worktrees/...`, which was confusing and split state.
- Opencode runs needed clearer observability (events, provider label, server attach), safer bash policy (no `git commit`/`merge`/`rebase`), and post-success **Gradle assemble** verification.

## What changed

### Task sandboxes (single place for code edits)

- **`src/worktree.py`**: `ensure_task_worktree_dir()` — resolves project from DB path / `TRACKER_PROJECT` / explicit `project=`; rejects `projects/<P>` as a stored worktree and **coerces** to `worktrees/<P>/task-<N>`; updates SQLite when repaired.
- **`orchestrator.py`**: Always runs `ensure_task_worktree_dir` before spawning the coder so bad `worktree` rows self-heal.
- **`agents/android_coder.py`**: On startup, `ensure_task_worktree_dir` + `chdir` so opencode `--dir`, Gradle, and recovery use the same root.
- **`run_android_coder.sh`**: Starts Python from `REPO_ROOT` (not `projects/DemoApp`); documents template vs worktree; optional `seed.py` when DB is missing.

### Opencode / Gemini path (`implementation: gemini`)

- Attach to **`http://localhost:4096`**, stream stdout, emit **`agent_output_line`** / **`agent_heartbeat`**, optional **inactivity timeout** and recovery from opencode DB on timeout.
- Event **`provider`** uses **`opencode/<model>`** (from `gemini_model` in YAML).
- **`RUN_TESTS.sh`** presence check and **`assembleDebug`** after success JSON.
- Stricter **`BASH_DENY`** for destructive git operations.

### Config & tooling

- **`agent_config.yml`**: Model (e.g. Gemini 3.1 Pro custom tools), timeouts, inactivity; **`agent_config.json`** removed.
- **`agents/runner.py`**: Related spawn / env behavior as needed for the above flow.
- **`src/runtime_paths.py`**: `infer_project_from_tracker_db()` for DB layout discovery.
- **Tests**: `test_android_coder.py`, `test_worktree.py`, `test_runtime_paths.py` updated for new layout and mocks.
- **`uv.lock`**: Lockfile added for reproducible installs where `uv` is used.

## How to verify

```bash
.venv/bin/python -m pytest tests/ -q
```

Run a task via orchestrator or `./run_android_coder.sh` and confirm `agent_launch` / `cwd` and files land under `worktrees/DemoApp/task-<N>`.

## Notes for reviewers

- Canonical **`projects/DemoApp`** remains the **copy source** only; task work belongs under **`worktrees/DemoApp/task-<task_number>`**.
- **`seed.py`** still loads `tasks/DemoApp/*.md` only when **`database/DemoApp/tasks.db` is missing**; re-seed manually if specs change and DB already exists.
