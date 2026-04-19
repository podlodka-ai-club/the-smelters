# Multi-Agent Dev Assistant

This repository contains the orchestration layer for a two-agent development system built on the Claude Agent SDK. The root project does not implement product logic itself; it manages tasks, routes them to the correct repository in `projects/`, and tracks execution.

## Table Of Contents

- [What Is Here](#what-is-here)
- [Pipeline](#pipeline)
- [Scripts And Modules](#scripts-and-modules)
- [Supported Agents](#supported-agents)
- [Adding A New Agent Provider](#adding-a-new-agent-provider)
- [Adding Another Agent SDK](#adding-another-agent-sdk)
- [Adding Platform-Specific Agents](#adding-platform-specific-agents)
- [Getting Started](#getting-started)
- [Adding A New Project](#adding-a-new-project)
- [How To Verify The System](#how-to-verify-the-system)

## What Is Here

- `tasks/` stores shared task specs in Markdown. Each file must include `Project: <folder_name>`.
- `projects/` stores target repositories the agents work on.
- `projects/python_fixture/` is a sample Python repo with intentionally failing behavior and matching tests. It exists to prove that the orchestration pipeline works before pointing the system at a real Android project.

The Python fixture is not part of the orchestrator runtime itself. It is a controlled target repo with 5 known bugs in small modules like `calc`, `strings`, `http_client`, `sorting`, and `cache`. The task files in `tasks/` all point at `Project: python_fixture`, so new contributors can run the full system against a predictable example first.

After cloning this repository, `projects/python_fixture/` is ready to use as a normal folder. The orchestrator copies the target project into `worktrees/<project>/task-N`, initializes a temporary git repo inside that task directory, and uses that sandbox for coder/reviewer diffing.

## Pipeline

```text
tasks/*.md
  -> seed.py
  -> tasks.db
  -> orchestrator.py
  -> projects/<task.project>
  -> worktrees/<project>/task-N
  -> agents/coder.py
  -> agents/reviewer.py
  -> events.jsonl
  -> printer.py / tui.py
```

1. `seed.py` reads `tasks/*.md`, extracts `Project: ...`, validates `projects/<name>` exists, and inserts tasks into `tasks.db`.
2. `orchestrator.py` claims the next ready task, resolves its target repo from `task.project`, copies it into a task sandbox, and initializes a temporary git repo there for diffing and review.
3. `agents/coder.py` works inside that worktree and applies the requested fix.
4. `agents/reviewer.py` verifies the change and approves or rejects it.
5. `src/tracker.py` persists state transitions, while `src/events.py` writes the event log consumed by `printer.py` and `tui.py`.

## Scripts And Modules

- `seed.py`: load Markdown tasks into SQLite.
- `orchestrator.py`: main task loop and retry logic.
- `printer.py`: plain terminal event stream.
- `tui.py`: Textual dashboard for live monitoring.
- `agents/runner.py`: subprocess wrapper for coder/reviewer agents.
- `agents/fake_coder.py`, `agents/fake_reviewer.py`: deterministic test doubles used in automated tests.
- `src/project_profile.py`: detects whether a target repo looks like Python, Android/Gradle, or generic.
- `src/worktree.py`: task sandbox creation and cleanup.

## Supported Agents

The orchestrator currently supports 4 agent roles:

- `coder`: the real implementation agent powered by the Claude Agent SDK. It edits code inside the task worktree and runs project verification commands.
- `reviewer`: the real review agent powered by the Claude Agent SDK. It checks verification results and inspects the diff before approving or rejecting a task.
- `fake_coder`: a deterministic test double used in automated tests and dry-runs. It simulates success, crash, or timeout without calling an external API.
- `fake_reviewer`: a deterministic test double used in automated tests and dry-runs. It simulates approval, rejection, malformed output, or retry flows.

In normal usage, `orchestrator.py` runs `coder` and `reviewer`. In tests, the suite often swaps them for `fake_coder` and `fake_reviewer` to verify orchestration logic without network calls.

## Adding A New Agent Provider

The current real agents are Claude-based, but the orchestration layer is provider-agnostic at the process boundary. `agents/runner.py` launches `python -m agents.<role> <task_id>`, so a new provider only needs to implement the same module contract.

To add providers such as OpenAI, OpenRouter, or Gemini:

1. Create new modules under `agents/`, for example `agents/openai_coder.py` and `agents/openai_reviewer.py`.
2. Load the task from `TRACKER_DB` and `TASKS_ROOT`, just like the existing `coder.py` and `reviewer.py`.
3. Run the provider SDK or HTTP client from inside the task worktree.
4. Keep the output contract unchanged:
   - coder must finish with one final JSON line like `{"ok": true, "summary": "..."}`
   - reviewer must finish with one final JSON line like `{"approved": true|false, "notes": "..."}`
5. Respect the same behavior expectations:
   - coder edits code and runs verification
   - reviewer is read-only and decides approve vs reject
6. Provide provider-specific credentials through environment variables, for example `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or `GEMINI_API_KEY`.

Common provider credentials:

- `ANTHROPIC_API_KEY` for Claude-based agents
- `OPENAI_API_KEY` for OpenAI-based agents
- `OPENROUTER_API_KEY` for OpenRouter-based agents
- `GEMINI_API_KEY` for Gemini-based agents

If a provider needs extra configuration such as base URLs, model names, or organization IDs, keep those in environment variables too. Do not hardcode secrets or provider settings inside agent modules.

Minimal checklist for any new agent module:

- It must be runnable as `python -m agents.<role> <task_id>`.
- It must exit non-zero on crash or timeout-worthy failure.
- It must print the final machine-readable JSON on the last non-empty stdout line.
- It should keep scope narrow and work only inside the assigned worktree.

Example naming scheme:

- `openai_coder` / `openai_reviewer`
- `openrouter_coder` / `openrouter_reviewer`
- `gemini_coder` / `gemini_reviewer`

The orchestration API already supports swapping roles programmatically through `Orchestrator(coder_role=..., reviewer_role=...)`. If you want provider selection from the command line, add CLI flags in `orchestrator.py` that map to those role names.

## Adding Another Agent SDK

Yes: the README now documents provider modules, but the real compatibility boundary is broader than a single provider. You can replace the current Claude Agent SDK with any other agent SDK as long as the new implementation keeps the same external contract expected by `agents/runner.py` and `orchestrator.py`.

What the orchestration layer expects from any SDK-backed agent:

- The agent is launched as a Python module: `python -m agents.<role> <task_id>`.
- It reads task context from `TRACKER_DB` and `TASKS_ROOT`.
- It runs inside the assigned task sandbox.
- It exits with code `0` on success and non-zero on failure.
- Its last non-empty stdout line is strict JSON:
  - coder: `{"ok": true, "summary": "..."}`
  - reviewer: `{"approved": true|false, "notes": "..."}`

Recommended way to support another SDK:

1. Create a new wrapper module in `agents/`, for example `agents/openai_coder.py`.
2. Keep task loading and prompt construction local to this repository.
3. Put only the SDK-specific query loop, tool wiring, and auth handling behind that wrapper.
4. Normalize the SDK response into the same final JSON contract.
5. Map SDK failures, timeouts, and malformed responses to non-zero exit codes or rejected reviewer verdicts.

In practice, each SDK wrapper should handle:

- authentication via env vars
- model selection
- tool permissions or tool-calling setup
- streaming vs non-streaming responses
- extraction of the final text payload
- conversion of provider-specific output into the repository's standard JSON result

Supported examples of alternative SDK families:

- OpenAI Agents SDK or plain OpenAI Responses API wrapper
- OpenRouter HTTP or SDK wrapper
- Gemini SDK wrapper
- any custom in-house agent runtime, as long as it preserves the same process contract

The clean long-term design is to keep the SDK-specific code thin and isolated inside provider modules, while `seed.py`, `orchestrator.py`, `src/tracker.py`, and `agents/runner.py` remain unchanged. If adding a new SDK requires changing those core files, the SDK boundary is too leaky and should be refactored.

## Adding Platform-Specific Agents

Provider and platform are separate concerns. A provider answers "which API runs the model"; a platform agent answers "what kind of codebase and tooling does this agent specialize in".

Examples of platform-specific roles:

- `android_coder` / `android_reviewer`
- `ios_coder` / `ios_reviewer`
- `python_coder` / `python_reviewer`

You can also combine both dimensions in one module name when needed:

- `openai_android_coder`
- `gemini_ios_reviewer`
- `openrouter_android_reviewer`

To add a platform-specific agent:

1. Create a new module in `agents/`.
2. Start from the closest existing implementation, usually `agents/coder.py` or `agents/reviewer.py`.
3. Change the system prompt and verification guidance for the target platform.
4. Keep the same input and output contract used by `agents/runner.py`.
5. Make sure the module knows the platform's standard verification commands.

Typical platform guidance:

- Android coder/reviewer: use Gradle tasks such as `./gradlew testDebugUnitTest`, `./gradlew assembleDebug`, and project-specific lint tasks.
- iOS coder/reviewer: use `xcodebuild test`, `xcodebuild build`, simulator-specific test commands, or Fastlane if the repo standardizes on it.
- Python coder/reviewer: use `pytest` or the repo's existing Python test command.

When platform agents become common, the next clean step is to add explicit role selection in `orchestrator.py`, for example `--coder-role android_coder --reviewer-role android_reviewer`, instead of only wiring them programmatically.

## Getting Started

```bash
uv venv
uv pip install -e ".[dev]"
.venv/bin/python seed.py
.venv/bin/python orchestrator.py --watch
```

In another terminal, watch execution with either:

```bash
.venv/bin/python printer.py
.venv/bin/python tui.py
```

## Adding A New Project

To connect a new repository to the orchestrator, add both the project repo and at least one task spec.

1. Copy or clone the target repository into `projects/<project_name>/`.
2. Ensure the project already builds or tests locally with its own commands.
4. Add one or more task files to `tasks/` and point them at the repo with `Project: <project_name>`.
5. Run `seed.py` to load those tasks into `tasks.db`.
6. Run `orchestrator.py --watch` to let the agents pick them up.

Minimum project requirements:

- The repo must live under `projects/`.
- The repo should expose a clear verification path, for example `pytest` for Python or `./gradlew testDebugUnitTest` for Android.
- The task spec must describe the expected fix clearly enough for coder and reviewer agents to act on it.

Example setup:

```bash
git clone <repo-url> projects/my_android_app
```

Example task file:

```md
Project: my_android_app

# Fix login crash on empty password

## Context
- Repro: open login screen and submit with an empty password
- Expected: validation error is shown instead of a crash

## Acceptance
- Relevant tests pass
- No unrelated files are changed
```

Then load and run:

```bash
.venv/bin/python seed.py
.venv/bin/python orchestrator.py --watch
```

## How To Verify The System

Use the Python fixture first. It is the reference example for onboarding and regression testing.

```bash
.venv/bin/pytest
```

Expected result: the repository test suite passes, including the integration path that seeds root `tasks/`, targets `projects/python_fixture/`, and closes all 5 sample tasks with fake agents.

Live agent smoke tests require `ANTHROPIC_API_KEY`:

```bash
ANTHROPIC_API_KEY=... .venv/bin/pytest -m live
```
