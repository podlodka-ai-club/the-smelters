# Project-First Runtime Design

## Summary

The orchestration system will be restructured so that every runtime action is scoped to one explicit project. A project becomes the unit of isolation for repositories, task specs, task state, event logs, worktrees, and project-specific integration tests.

The command-line interface must require `--project <name>` for runtime entry points. Task numbers are local to a project and become the user-facing identifier. The database keeps an internal row id, but user-facing flows use `task_number`.

## Goals

- Make every runtime command operate on exactly one project.
- Store task specs, databases, events, and worktrees under project-specific paths.
- Make task numbers local to a project and stable across reseeding.
- Remove user-facing dependence on the database row id.
- Keep shared orchestration code in one place instead of copying it into every project directory.

## Non-Goals

- Rewriting agent prompts or agent behavior outside of project scoping.
- Creating separate copies of orchestrator source code per project.
- Preserving backward compatibility with the old global `tasks.db` and flat runtime layout.

## Target Layout

```text
projects/<project>/
tasks/<project>/
database/<project>/tasks.db
database/<project>/events.jsonl
worktrees/<project>/
tests/<project>/
```

Shared unit tests for generic orchestration logic remain at top-level under `tests/`. Project-specific integration and fixture tests move under `tests/<project>/`.

## Command Model

The following commands require `--project <name>`:

- `seed.py`
- `orchestrator.py`
- `printer.py`
- `tui.py`

Examples:

```bash
.venv/bin/python seed.py --project DemoApp
.venv/bin/python orchestrator.py --project DemoApp --watch
.venv/bin/python orchestrator.py --project DemoApp --task 7 --watch
.venv/bin/python printer.py --project DemoApp
.venv/bin/python tui.py --project DemoApp
```

Runtime paths are derived from the selected project:

- repo: `projects/<project>/`
- tasks: `tasks/<project>/`
- db: `database/<project>/tasks.db`
- events: `database/<project>/events.jsonl`
- worktrees: `worktrees/<project>/`

## Task Identity

User-facing task identity is the task number inside the project, not the database row id.

Rules:

- `task_number` is parsed from the task filename.
- `1-divide-by-zero.md` yields `task_number = 1`.
- task numbers are unique only within a project.
- the database keeps an internal `id` for joins and updates, but the UI and CLI use `task_number`.

`--task <n>` is interpreted as the project-local task number, so it is only valid together with `--project <name>`.

## Database Design

Each project has its own SQLite database at `database/<project>/tasks.db`.

The `tasks` table should contain:

- `id` integer primary key
- `task_number` integer not null
- `title` text not null
- `spec_path` text not null
- `status` text not null
- `attempts` integer not null default 0
- `worktree` text
- `branch` text
- `review_notes` text
- `created_at` text not null
- `updated_at` text not null

Constraints:

- `UNIQUE(task_number)`

Because the database is project-local, the `project` column is no longer needed.

## Seeding

`seed.py --project <name>` reads only `tasks/<project>/`.

Seeding behavior:

- validate that `projects/<project>/` exists
- parse each task file in `tasks/<project>/`
- extract `task_number` from the filename
- extract `title` from the first markdown heading
- preserve `spec_path` relative to repo root, such as `tasks/DemoApp/7-share-download-functionality.md`
- insert missing tasks into `database/<project>/tasks.db`
- identify existing tasks by `task_number`, not by row id

If a filename does not start with an integer prefix followed by a separator, seeding should fail with a clear assertion error.

## Orchestrator

`orchestrator.py --project <name>` only reads from that project's database and only works against that project's repository and task folder.

Behavior:

- open `database/<project>/tasks.db`
- write events to `database/<project>/events.jsonl`
- create worktrees under `worktrees/<project>/`
- use `projects/<project>/` as the target repo
- resolve task specs from the selected project's task folder

Task claiming:

- default run: claim the next `ready` task ordered by `task_number`
- `--task <n>`: claim only the matching `ready` task with that `task_number`

If `--task <n>` points at a non-ready or missing task, the orchestrator does nothing and exits or waits, depending on `--watch`.

## Tracker API Changes

The tracker becomes project-local because each `Tracker` instance points at one project's database.

Key changes:

- add `task_number` to the `Task` model
- remove `project` from the `Task` model for project-local operations
- `insert_task(...)` accepts `task_number`
- claim queries order by `task_number`
- claim queries filter by `task_number` instead of row id for CLI task selection

## TUI and Printer

`tui.py --project <name>` and `printer.py --project <name>` read only the selected project's database and event log.

UI behavior:

- show `task_number` as the visible task identifier
- stop showing the internal row id as the main task number
- keep status, attempts, and title visible

## Tests

Test structure:

- shared orchestration unit tests stay under top-level `tests/`
- project-specific integration tests move under `tests/<project>/`

Required coverage:

- seeding a single selected project
- parsing `task_number` from filenames
- rejecting invalid task filenames
- project-local database path resolution
- project-local event path resolution
- task claiming ordered by `task_number`
- `--task <n>` selecting only one project-local task
- TUI showing `task_number`

## Migration Strategy

Migration will be handled in-place on the new branch and does not need to preserve the previous runtime databases.

Steps:

1. Introduce project-local path resolution helpers and require `--project` in runtime CLIs.
2. Add `task_number` to models and tracker schema.
3. Update seeding to operate on one project and parse filenames.
4. Update orchestrator, printer, and TUI to use project-local paths and task numbers.
5. Move project-specific tests into `tests/<project>/`.
6. Update README examples and operational guidance.
7. Remove assumptions tied to the old global database and global event log.

## Risks

- Mixed assumptions between row id and `task_number` can cause the wrong task to be claimed or displayed.
- Leaving any runtime command without mandatory `--project` would preserve ambiguous global behavior.
- Tests that still assume global paths or a `project` column in task rows will fail until updated consistently.

## Acceptance Criteria

- Runtime CLIs require `--project`.
- Each project uses its own task database and event log under `database/<project>/`.
- Task numbers are parsed from filenames and used in CLI and TUI.
- `--task <n>` refers to project-local task numbers.
- Worktrees and tasks are resolved only within the selected project.
- The full automated test suite passes after the migration.
