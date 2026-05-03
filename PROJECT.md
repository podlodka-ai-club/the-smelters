# Project Overview

This project builds a multi-agent development assistant that takes engineering tasks, executes implementation workflows in isolated worktrees, and produces reviewable changes with automated validation.

The repository now includes **two working orchestration pipelines**:

1. **Custom orchestrator** (`orchestrator.py`) for queue-driven task execution from SQLite.
2. **Agno orchestrator** (`agno_orchestrator.py`) for explicit Android TDD flows based on the [Agno](https://github.com/agno-agi/agno) workflow engine.

## Goals

For the project to be considered complete, the system should:

- Ingest tasks from a tracker or queue.
- Implement code changes with agents.
- Run verification and retry/fix when checks fail.
- Work against real repositories in `projects/`.
- Produce PR-ready output.

## Current Architecture (Updated)

### 1) Custom pipeline (SQLite task queue)

- Reads `tasks/<project>/*.md` via `seed.py` into `database/<project>/tasks.db`.
- `orchestrator.py` claims tasks and runs coder/reviewer roles in `worktrees/<project>/task-N`.
- Uses agent modules in `agents/` with shared prompts/utilities from `shared/`.
- Tracks task status and events in SQLite + JSONL logs.

### 2) Agno pipeline (new)

- Entry point: `agno_orchestrator.py --task <task-file.md>`.
- Uses dedicated Agno agents in `agno_agents/` and tools in `agno_tools/`.
- Android-first TDD sequence:
  - class mode: `test_writer_agent` -> `impl_agent` -> `lint_fix_agent` -> `test_run_agent`
  - smelters mode: `coder` -> `code_checker` -> `pr_create_step` -> `pr_reviewer_step` -> `pr_comment_publish`
- Supports conditional retries and optional human-review gates (`--auto` to run unattended).
- Uses Agno workflow/session state and an ephemeral SQLite DB for orchestration metrics.

## Tech Stack

- **Language/runtime:** Python (`uv`, virtual environment).
- **Orchestration:** custom Python orchestrator + Agno Workflow engine.
- **Agent backends:** Claude CLI/SDK and Gemini (via opencode / Agno model adapters).
- **Storage:** SQLite for task and run state.
- **Targets:** primarily Android/Kotlin repositories with clear build/test commands.

## Task And Repo Conventions

- Target repositories live in `projects/<project>/`.
- Tasks live in `tasks/<project>/`.
- Task files should include `Project: <project>` for seeded custom-pipeline runs.
- Agno tasks should include Android metadata headers (`**Module:**`, `**Package:**`, `**Class:**`) for class-level TDD execution.

## Operations Quickstart

```bash
uv venv
uv pip install -e ".[dev]"
```

### Custom pipeline

```bash
.venv/bin/python seed.py --project <project>
.venv/bin/python orchestrator.py --project <project> --watch
.venv/bin/python tui.py --project <project>
```

### Agno pipeline

```bash
.venv/bin/python agno_orchestrator.py \
  --task tasks/DemoApp/007-favorites-vm.md \
  --repo podlodka-ai-club/the-smelters \
  --github-token-env GITHUB_TOKEN \
  --task-context-mode inline \
  --reviewer claude \
  --auto
```

## Delivery Context

- Main repository: [podlodka-ai-club/the-smelters](https://github.com/podlodka-ai-club/the-smelters)
- Task tracker (planned): [Linear CLI](https://github.com/schpet/linear-cli)
- Linear board: [AI Hacker Sprint team board](https://linear.app/aihackersprint/team/AIH/active)
- Reference orchestrators:
  - [egv/yolo-runner](https://github.com/egv/yolo-runner)
  - [stepango/grkr](https://github.com/stepango/grkr)
- Mind map: [Project board](https://app.holst.so/board/2f7472e9-dffd-463f-9656-738d0a2a73d9)

## Roadmap (Next Milestones)

1. **Task source integration**
   - Add production-grade task ingestion from Linear into project-scoped queues.
   - Normalize incoming task format into repository conventions before execution.

2. **Autonomous PR delivery**
   - Add branch lifecycle automation and PR creation via `gh`.
   - Attach run summaries (tests, lint, checker verdict) to PR description.

3. **Retry and repair hardening**
   - Improve failure classification (lint/test/build/infrastructure) and targeted retries.
   - Add guardrails for max attempts, cooldowns, and explicit terminal failure reasons.

4. **Provider expansion**
   - Add additional agent provider wrappers while preserving current runner contracts.
   - Make provider selection explicit per role and per run.

5. **Android workflow maturity**
   - Expand Agno task parsing validation and preflight checks for module/package/class mapping.
   - Improve deterministic command execution and artifact capture for Gradle-based runs.

6. **Observability and operations**
   - Add richer run metrics and step timing dashboards.
   - Define operational playbooks for reruns, stuck tasks, and incident triage.

