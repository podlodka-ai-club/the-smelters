# Multi-Agent Dev Assistant

This repository contains the orchestration layer for a multi-agent development system. It manages tasks, routes them to the correct repository in `projects/`, and tracks execution.

The project ships **two independent pipelines** that solve the same problem with different trade-offs:

1. **Custom orchestrator** (`orchestrator.py`) — a hand-rolled task loop that drives Claude-SDK agents in `agents/` directly. Simple coder → reviewer loop with retry on rejection.
2. **Agno orchestrator** (`agno_orchestrator.py`) — a richer multi-step pipeline built on the [Agno](https://github.com/agno-agi/agno) framework using agents in `agno_agents/`. Supports class-mode Android TDD and smelters-mode checker→PR→review automation.

Both pipelines share constants, prompts, and helper utilities under `shared/`. See [Two Pipelines](#two-pipelines) below for when to use which.

## Table Of Contents

- [Two Pipelines](#two-pipelines)
- [What Is Here](#what-is-here)
- [Pipeline](#pipeline)
- [Agno Workflow (alternate orchestrator)](#agno-workflow-alternate-orchestrator)
- [Scripts And Modules](#scripts-and-modules)
- [Supported Agents](#supported-agents)
- [Adding A New Agent Provider](#adding-a-new-agent-provider)
- [Adding Another Agent SDK](#adding-another-agent-sdk)
- [Adding Platform-Specific Agents](#adding-platform-specific-agents)
- [Configuration](#configuration)
- [Getting Started](#getting-started)
- [Adding A New Project](#adding-a-new-project)
- [How To Verify The System](#how-to-verify-the-system)

## Two Pipelines

| | `orchestrator.py` (custom) | `agno_orchestrator.py` (Agno) |
|---|---|---|
| **Framework** | None — direct subprocess + Claude Agent SDK | [Agno](https://github.com/agno-agi/agno) framework (its `Workflow` engine) |
| **Agents** | `agents/coder.py`, `agents/reviewer.py`, `agents/code_checker.py`, `agents/android_coder.py` | `agno_agents/test_writer_agent.py`, `agno_agents/impl_agent.py`, `agno_agents/lint_fix_agent.py`, `agno_agents/test_run_agent.py`, `agno_agents/code_checker.py`, `agno_agents/android_coder.py` |
| **Steps** | coder → reviewer (loop on reject, configurable max attempts) | class mode: test_writer → impl → lint_fix → test_run; smelters mode: coder → checker → create PR → local reviewer → PR comment |
| **State** | SQLite (`database/<project>/tasks.db`) + JSONL events | Agno session state + ephemeral SQLite for metrics |
| **Scope** | One task at a time, project-agnostic (Python, Android, generic) | Single Android TDD target class at a time |
| **Backends** | Claude (Anthropic SDK) or Gemini (via `opencode` CLI) | Claude or Gemini via Agno's model adapters |
| **Human review** | Not built-in (orchestrator runs to completion) | Optional human-review gates between steps (`--auto` disables) |
| **Use when** | You have many independent tasks queued in the tracker DB and want autonomous batch processing. | You're doing TDD on a specific Android class and want fine-grained step control. |

Both pipelines coexist; pick whichever fits the workload. Shared system prompts (`shared/prompts.py`), validation utilities (`shared/checker_utils.py`), constants (`shared/constants.py`), and SDK helpers (`shared/agent_base.py`) keep them aligned.

## What Is Here

- `tasks/<project>/` stores task specs for one selected project. Each file must include `Project: <folder_name>`.
- `projects/` stores target repositories the agents work on.
- `database/<project>/tasks.db` stores task state for one project.
- `database/<project>/events.jsonl` stores the event stream for one project.
- `worktrees/<project>/` stores isolated task sandboxes for one project.
- `projects/python_fixture/` is a sample Python repo with intentionally failing behavior and matching tests. It exists to prove that the orchestration pipeline works before pointing the system at a real Android project.

The Python fixture is not part of the orchestrator runtime itself. It is a controlled target repo with 5 known bugs in small modules like `calc`, `strings`, `http_client`, `sorting`, and `cache`. The task files in `tasks/python_fixture/` all point at `Project: python_fixture`, so new contributors can run the full system against a predictable example first.

After cloning this repository, `projects/python_fixture/` is ready to use as a normal folder. The orchestrator copies the target project into `worktrees/<project>/task-N`, initializes a temporary git repo inside that task directory, and uses that sandbox for coder/reviewer diffing.

## Pipeline

### Custom orchestrator (`orchestrator.py`)

```text
tasks/<project>/*.md
  -> seed.py --project <project>
  -> database/<project>/tasks.db
  -> orchestrator.py --project <project>
  -> projects/<project>
  -> worktrees/<project>/task-N
  -> agents/coder.py  (or agents/android_coder.py for Android projects)
  -> agents/reviewer.py
  -> database/<project>/events.jsonl
  -> printer.py --project <project> / tui.py --project <project>
```

1. `seed.py --project <name>` reads `tasks/<project>/*.md`, extracts `Project: ...`, validates `projects/<name>` exists, parses the task number from the filename, and inserts tasks into `database/<project>/tasks.db`.
2. `orchestrator.py --project <name>` claims the next ready task from that project's database, copies `projects/<project>/` into a task sandbox, and initializes a temporary git repo there for diffing and review.
3. `agents/coder.py` (or `agents/android_coder.py`) works inside that worktree and applies the requested fix.
4. `agents/reviewer.py` verifies the change and approves or rejects it.
5. `src/tracker.py` persists state transitions, while `src/events.py` writes the project-local event log consumed by `printer.py` and `tui.py`.

### Agno orchestrator (`agno_orchestrator.py`)

```text
tasks/<Project>/<task>.md
  -> agno_orchestrator.py --task <path-to-task.md>
  -> class mode:
       agno_agents/test_writer_agent.py   (write failing test)
       agno_agents/impl_agent.py          (implement to pass test)
       agno_agents/lint_fix_agent.py      (loop until lint clean)
       agno_agents/test_run_agent.py      (run tests in real Gradle)
  -> smelters mode:
       coder -> checker
       agno_tools/pr_create_step.py       (create/reuse PR)
       agno_tools/pr_reviewer_step.py     (local reviewer with task context)
       agno_tools/pr_comment_publisher.py (publish/update PR comment)
```

Run directly against a task spec, no tracker DB or seed step required:

```bash
.venv/bin/python agno_orchestrator.py --task tasks/DemoApp/007-favorites-vm.md --auto
```

The orchestrator parses `**Module:**`, `**Package:**`, `**Class:**` headers from the task markdown, derives the matching test/impl file paths under the Gradle module, and walks each agent step with conditional retries (lint fails → re-run lint_fix; tests fail → re-run impl). The `--auto` flag bypasses Agno's human-review gates so it runs unattended.

In smelters mode (`Project: <Name>` task format), the orchestrator runs coder/checker loop first, then on checker success creates or reuses a PR, runs a local reviewer, and publishes/upserts a PR comment via `gh api`. Full **Smelters YAML + CLI reference** is in the next subsection.

**PR gate (checker JSON, not subprocess exit).** PR creation and the reviewer/comment steps run only after the checker output is accepted as passed (see `checker_passed_from_content` in `src/smelters_flow_state.py`: a JSON object line containing `"status": "passed"`). The post-loop `Condition` reads that verdict from nested `CoderCheckerLoop` step outputs (Agno’s `previous_step_content` after a `Loop` is only a short summary string). For the opencode checker, exit code 0 does not imply pass; if the model omits valid contract JSON, the step normalizes to `status: "error"` with `scope: "checker"` so the gate stays closed without looking like a test failure. Tooling failures (timeouts, non-zero exit, provider/model errors) use the same `error` + `scope: "checker"` shape; the coder/checker loop stops on that outcome without opening the PR path.

**PR create — default git behavior (`agno_tools/pr_create_step.py`).** When `--head-branch` is **omitted**, Smelters prepares the PR like this: (1) **Fail fast** if the working tree has any local change **outside** the Gradle project directory (`--project` / `project_scope_posix`)—commit, stash, or discard those paths first; only the project tree may be dirty. (2) **`--base-branch` must be `main`** (default); other bases are rejected unless you use `--head-branch` and manage branches yourself. (3) `git fetch origin main`, checkout **`main`**, and **`git pull --ff-only origin main`** (fails if your local `main` is not a fast-forward of the remote—fix `main` and retry). (4) Create and push a new branch named from the **task file path** (e.g. `tasks/DemoApp/9-story.md` → `smelters/tasks-demoapp-9-story`), with tip at updated `main`, containing **only** changes under the project directory (stashed uncommitted work plus commits on your previous `HEAD` that touched that tree). If that branch name already exists locally or on `origin`, the step fails—delete/rename it or pass `--head-branch`. (5) With **`--head-branch`**, Smelters skips the main/task-branch automation and checks out that branch before staging/committing under the project scope only (PRs may still include unrelated commits on that head—use the default flow for a clean, single-purpose branch).

**Whole-flow failure and exit code.** If a run finishes without opening that PR path (for example the coder/checker loop hits `--max-iterations` without a passing checker), the process exits with code 1, prints an `SMELTERS FLOW FAILED` banner to stderr, and writes `projects/<Name>/.smelters/resume.json` with the last checker raw output plus metadata (`task_path`, `repo`, `max_iterations`, timestamp). That directory is gitignored. The banner explains the situation using the last captured checker step: for example, a valid `"status": "failed"` JSON (tests/build still failing) is described differently from missing checker contract JSON, checker tooling errors (`"status": "error"`, `"scope": "checker"`), or an empty capture from the event log.

**Resume.** Re-run with a higher `--max-iterations` on the same task and project; the Gradle tree already reflects the last attempt. Optionally add `--resume` so the first coder iteration sees the saved checker output (task preamble for Claude/Gemini agents; `previous_step_content` for `claude-cli` / `opencode` coders). The resume file is removed when the PR-create step runs (checker gate opened). A concrete suggested command is included in the failure banner.

**Live output and `--debug-logging`.** Model and tool activity for Agno API agents is streamed to the terminal by default (`print_response` with streaming). Pass **`--debug-logging`** to also (1) set Agno agent + workflow loggers to DEBUG and (2) **stream combined stdout/stderr** from Smelters **opencode** subprocess steps (coder, checker, reviewer) to the terminal while still capturing the full transcript for the workflow. This is separate from the API token stream; use `2>&1 | tee run.log` if you want one file with everything. You can also set `debug_logging: true` in `agent_config.yml` (boolean or `true`/`yes` string). Non-opencode subprocess backends (`claude-cli`) are unchanged by the opencode streaming half of this flag.

### Smelters — YAML keys and CLI parameters (`agno_orchestrator.py`)

**Recommended:** configure backends and opencode models in `agent_config.yml` and **do not** pass `--coder`, `--checker`, or `--reviewer` on the command line. Those three flags exist only to **override** the YAML values for a single run (you can pass one, two, or all three).

**Custom YAML path:** `--agent-config PATH` loads that file. If you omit it, the orchestrator loads the first existing file among `$REPO_ROOT/agent_config.yml` and `./agent_config.yml`; if neither exists, built-in defaults apply (see `shared/agent_base.DEFAULT_CONFIG` and `src/smelters_yaml.py` fallbacks).

**YAML keys for Smelters** (in addition to shared keys like `agent_timeout`, `opencode_server_url`):

| Key | Purpose |
|-----|---------|
| `smelters_coder_backend` | `claude` \| `gemini` \| `claude-cli` \| `opencode` |
| `smelters_checker_backend` | `gemini` \| `claude-cli` \| `opencode` |
| `smelters_reviewer_backend` | `claude` \| `opencode` |
| `opencode_coder_model` | `opencode run --model …` when coder backend is `opencode` |
| `opencode_checker_model` | Same when checker backend is `opencode` |
| `opencode_reviewer_model` | Same when reviewer backend is `opencode` |
| `debug_logging` | off | When true, same as `--debug-logging` (OR with CLI): Agno DEBUG loggers plus live opencode subprocess output for Smelters. |

**Smelters-related CLI flags** (all optional except `--task` and, for PR flow, repo/token as noted):

| Flag | Default | Notes |
|------|---------|--------|
| `--task` | *(required)* | Path to task `.md` (`Project: …` first line for Smelters). |
| `--agent-config` | *(omit)* | Explicit path to YAML; else discover `agent_config.yml`. |
| `--project` | auto | Gradle root; usually `projects/<Name>` from task path. |
| `--coder` | from YAML | **Override** `smelters_coder_backend` only if needed. |
| `--checker` | from YAML | **Override** `smelters_checker_backend` only if needed. |
| `--reviewer` | from YAML | **Override** `smelters_reviewer_backend` only if needed. |
| `--coder-model` | `sonnet` | Only for `--coder claude-cli` (Claude Code CLI model). |
| `--checker-model` | `sonnet` | Only for `--checker claude-cli`. |
| `--max-iterations` | `4` | Coder ⇄ checker loop cap (`MAX_FIX_ITERATIONS`). |
| `--task-id` | *(omit)* | When set, persist Agno session under `database/<Project>/agno-session.sqlite` and emit events (see [Agno Workflow](#agno-workflow-alternate-orchestrator)). |
| `--resume` | off | Smelters only: require `projects/<Name>/.smelters/resume.json` and seed the first coder pass with `last_checker_output`. |
| `--repo` | *(none)* | **Required in Smelters** for PR create/review: `owner/name`. |
| `--base-branch` | `main` | PR base for `gh pr create`; must stay `main` for the default head-branch automation (see PR create above). |
| `--head-branch` | *(omit)* | Optional override: skip main/task-branch flow and use this branch as the PR head (advanced). |
| `--pr-title` | inferred | PR title override. |
| `--pr-body-file` | none | Markdown file for PR body (must exist if set). |
| `--github-token-env` | `GITHUB_TOKEN` | Env var **name** for `gh api` (`GH_TOKEN`). If unset, credentials come from `gh auth token` after `gh auth login`; if neither works, the run fails with a clear error. |
| `--task-context-mode` | `inline` | `inline` = embed task text in reviewer prompt; `path` = path only. |
| `--debug-logging` | off | Agno agent + workflow loggers at DEBUG; Smelters opencode steps stream child stdout/stderr live. Class and Smelters. |
| `--auto` | off | **Class mode only** — not Smelters; drops human-review gates in TDD pipeline. |

Example with **only YAML-driven backends** (no `--coder` / `--checker` / `--reviewer`):

```bash
# Optional if `gh auth login` already provides credentials:
# export GITHUB_TOKEN=…

uv run python agno_orchestrator.py \
  --task tasks/DemoApp/your-task.md \
  --repo your-org/the-smelters
```

Example using an alternate config file:

```bash
uv run python agno_orchestrator.py \
  --agent-config ./my-agent-config.yml \
  --task tasks/DemoApp/your-task.md \
  --repo your-org/the-smelters
```

Example **overriding only the checker** for one run (coder and reviewer still from YAML):

```bash
uv run python agno_orchestrator.py \
  --task tasks/DemoApp/your-task.md \
  --repo your-org/the-smelters \
  --checker gemini
```

## Agno Workflow (alternate orchestrator)

`agno_orchestrator.py` is a second orchestrator built on the [Agno](https://github.com/agno-agi/agno) workflow runtime. It runs the same `tasks/<project>/*.md` specs but bypasses `seed.py` / `tracker.py` / `worktrees/` — it operates directly on `projects/<project>/` and persists workflow state in its own SQLite. Use it when you want a streamed step view with rich live progress, retry-on-API-error resilience, and resume-from-last-step on crash.

Two task formats are auto-detected from the `.md` file:

- **smelters mode** — file starts with `Project: <Name>`. Open-ended PRD. The workflow runs `AndroidCoder ⇄ CodeChecker` in a loop: coder writes tests, implementation, and `RUN_TESTS.sh`; checker runs the script, parses Gradle XML reports, and emits a JSON verdict. On `failed`, the verdict (plus a diff of what the previous iteration changed) is fed back to the coder. Loop ends on `passed`, on checker tooling `error`/`scope: "checker"`, or after `MAX_FIX_ITERATIONS` (default 4). After a passing checker, the Smelters PR path (create/reuse PR → local reviewer → PR comment) runs as described above.
- **class mode** — file has `**Module:**` / `**Package:**` / `**Class:**` headers. Single-class TDD: `TestCase → TestWriter → Impl → LintLoop(detekt) → TestLoop(:module:test)`. Use `--auto` to drop human-review gates.

### Feedback loop, iteration cap, and resilience (smelters mode)

- **Cyclic state machine.** `Loop(steps=[coder, checker, diff_tracker], end_condition=_coder_checker_loop_finished, max_iterations=4)`: the loop stops when the last inner-step content parses as checker `passed`, or as checker infrastructure `error` with `scope: "checker"` (so a broken checker does not burn all iterations). The `diff_tracker` step uses `git stash create` to snapshot the worktree each iteration, so the next coder iteration receives a `PREVIOUS_ITERATION_DIFF` block describing exactly what its prior attempt changed. This prevents code thrashing where the coder keeps reverting useful edits.
- **Iteration cap.** Default `MAX_FIX_ITERATIONS = 4` (override with `--max-iterations N`). When the cap is hit without a passing verdict, an event of type `task_aborted` with `reason="MAX_FIX_ITERATIONS_REACHED"` is emitted.
- **Resume from SQLite.** When `--task-id <N>` is set, the Agno session is keyed as `task-<N>` and persisted at `database/<Project>/agno-session.sqlite`. If the run crashes (network blip, OOM, kill), re-running the same command resumes from the last cached step result instead of starting from iteration 1.
- **Retry/backoff on transient API errors.** The runner catches transient exceptions (rate limits, 502/503/504, timeouts, connection drops) and retries up to 3 times with exponential backoff (2s, 4s, 8s) before surfacing. Each catch emits an `agent_error_caught` event.

### Events (mappable to TUI)

When `--task-id` is set, structured events are appended to `events.jsonl` (default `database/<Project>/events.jsonl`, override with `--events-path` or `$EVENTS_PATH`). The Agno-specific event types:

| `actor` | `type` | fields |
|---|---|---|
| `orchestrator` | `loop_iteration` | `iteration`, `max` |
| `orchestrator` | `task_aborted` | `reason="MAX_FIX_ITERATIONS_REACHED"`, `iterations`, `max` |
| `orchestrator` | `agent_error_caught` | `error`, `attempt` |

These share the `events.jsonl` shape used by `printer.py` and `tui.py`, so live monitoring works the same way:

```bash
.venv/bin/python tui.py --project DemoApp
```

### Backends

- **coder**: `claude-cli`, `claude` (Anthropic API + Sonnet 4.6), `gemini`, or `opencode` (see `smelters_coder_backend` / `opencode_coder_model` in `agent_config.yml`).
- **checker**: `claude-cli`, `gemini`, or `opencode` (see `smelters_checker_backend` / `opencode_checker_model`).

`claude-cli` requires only that the `claude` binary be on `$PATH` (or `$CLAUDE_BIN` set). `claude` needs `ANTHROPIC_API_KEY`. `gemini` needs `GOOGLE_API_KEY`.

### Running

Smoke-run a smelters task with events + diff tracking + retry (SQLite resume when `--task-id` is set):

```bash
uv run --frozen -- python agno_orchestrator.py \
  --task tasks/DemoApp/10-gifloadresult-getornull.md \
  --task-id 10
```

Watch events live in another terminal:

```bash
tail -f database/DemoApp/events.jsonl
```

Other useful flags:

- `--coder gemini --checker gemini` — fully Gemini-backed.
- `--coder claude --checker claude-cli` — Anthropic API for coder, Claude CLI for checker.
- `--max-iterations 6` — bump the loop cap.
- `--events-path /tmp/run.jsonl` — write events somewhere other than the default.
- `--auto` (class mode only) — skip human-review gates after lint/test loops cap out.

A clean re-run without resuming the prior session:

```bash
rm -f database/DemoApp/agno-session.sqlite database/DemoApp/events.jsonl
```

## Scripts And Modules

Top-level entrypoints:

- `seed.py`: load Markdown tasks into SQLite.
- `orchestrator.py`: custom task loop with retry logic (uses `agents/`).
- `agno_orchestrator.py`: Agno-based multi-step orchestrator (uses `agno_agents/`).
- `printer.py`: plain terminal event stream.
- `tui.py`: Textual dashboard for live monitoring.

Custom-orchestrator agents (`agents/`):

- `agents/runner.py`: subprocess wrapper that launches an agent role as `python -m agents.<role> <task_id>` (or any dotted module path).
- `agents/coder.py`, `agents/reviewer.py`: generic Claude-SDK coder/reviewer.
- `agents/android_coder.py`, `agents/code_checker.py`: Android-specialized variants.

Agno-orchestrator agents (`agno_agents/`):

- `agno_agents/test_writer_agent.py`: writes the failing test for a class spec.
- `agno_agents/impl_agent.py`: implements the class to make the test pass.
- `agno_agents/lint_fix_agent.py`: fixes detekt/ktlint violations.
- `agno_agents/test_run_agent.py`: runs the Gradle test task and reports results.
- `agno_agents/code_checker.py`, `agno_agents/android_coder.py`: Agno wrappers for the same roles as in `agents/`.

Shared modules (`shared/`):

- `shared/agent_base.py`: config loading, Claude SDK message helpers, Gemini/`opencode` subprocess runner, bash deny-list permission factory.
- `shared/checker_utils.py`: JSON validation/clamping for code-checker output.
- `shared/constants.py`: bash deny patterns, timeout and size caps.
- `shared/prompts.py`: canonical system prompts (used by both pipelines).

Other:

- `src/project_profile.py`: detects whether a target repo looks like Python, Android/Gradle, or generic.
- `src/worktree.py`: task sandbox creation and cleanup.
- `tests/fixtures/fake_coder.py`, `tests/fixtures/fake_reviewer.py`: deterministic test doubles used by the test suite.

## Supported Agents

The custom orchestrator currently supports these agent roles:

- `coder`: the real implementation agent powered by the Claude Agent SDK. It edits code inside the task worktree and runs project verification commands.
- `reviewer`: the real review agent powered by the Claude Agent SDK. It checks verification results and inspects the diff before approving or rejecting a task.
- `android_coder`: Android-specialized coder with Gradle-aware system prompt and `RUN_TESTS.sh` generation. Auto-selected by `orchestrator.py` when `src/project_profile.py` detects an Android Gradle project.
- `code_checker`: read-and-execute verification agent that runs `RUN_TESTS.sh`, parses Gradle/JUnit output, and emits a strict JSON report.

The Agno orchestrator uses its own set of agents (`test_writer_agent`, `impl_agent`, `lint_fix_agent`, `test_run_agent`) chained by `agno_orchestrator.py`, plus shared roles like `code_checker` and `android_coder`.

For tests, deterministic doubles live under `tests/fixtures/`:

- `tests.fixtures.fake_coder`: simulates success, crash, or timeout without calling an external API.
- `tests.fixtures.fake_reviewer`: simulates approval, rejection, malformed output, or retry flows.

The runner accepts any dotted module path as a role, so tests pass `coder_role="tests.fixtures.fake_coder"` to swap in fakes without network calls.

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

## Configuration

### Gemini via opencode (android_coder default)

`android_coder` uses opencode with Gemini by default. Set the API key in **one** of these ways, in order of preference:

1. **`agent_config.yml`** (persists across sessions, no env juggling):
   ```yaml
   gemini_api_key: "AIza..."
   ```

2. **Environment variable** (shell must export it before running):
   ```bash
   export GOOGLE_GENERATIVE_AI_API_KEY="AIza..."
   ```
   > Note: opencode requires `GOOGLE_GENERATIVE_AI_API_KEY`, not `GEMINI_API_KEY`.
   > The agent sets both automatically when `gemini_api_key` is provided in config.

3. **`opencode auth`** (interactive, stored in opencode's own credential store).

Leave `opencode_server_url` empty in `agent_config.yml`. Standalone mode works correctly once the key is available.

### Android SDK (for Android projects)

`local.properties` with the SDK path is created automatically in each new worktree from `ANDROID_HOME`, `ANDROID_SDK_ROOT`, or the default macOS location `~/Library/Android/sdk`. No manual action needed as long as the SDK is installed.

If the build still fails with `SDK location not found`, set the variable explicitly:
```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
```

### Choosing backend per run (`--coder` / `--checker` / `--reviewer`)

For **`agno_orchestrator.py` Smelters mode**, prefer **YAML-only backends** and use the full flag list in **Smelters — YAML keys and CLI parameters** above. The table below targets the **legacy** `orchestrator.py` / class-style flows; it is not a substitute for the Smelters section.

The legacy orchestrator accepts `--coder` and `--checker` flags that override `agent_config.yml` without editing the file:

| Flag value | Backend | Auth required |
|---|---|---|
| `claude-cli` | Claude Code CLI | CLI auth |
| `claude` | Claude SDK path | `ANTHROPIC_API_KEY` |
| `gemini` | Gemini / opencode per project wiring | Google / opencode auth as configured |

Smelters PR/review flags (also documented in the Smelters subsection):

- `--repo owner/name` (required in smelters mode)
- `--github-token-env GITHUB_TOKEN` (variable optional if `gh` is logged in; Smelters fills from `gh auth token` when needed)
- `--task-context-mode inline|path` (default `inline`)
- optional: `--base-branch`, `--head-branch`, `--pr-title`, `--pr-body-file`

Optional `--coder-model` / `--checker-model` override the model when using `gemini`:

```bash
# Claude subscription for both (default recommended)
.venv/bin/python orchestrator.py --project DemoApp --task 10 \
  --coder claude-cli --checker claude-cli

# Gemini for both
.venv/bin/python orchestrator.py --project DemoApp --task 10 \
  --coder gemini --checker gemini

# Mixed: Gemini codes, Claude reviews
.venv/bin/python orchestrator.py --project DemoApp --task 10 \
  --coder gemini --checker claude-cli

# Mixed: Claude codes, Gemini reviews
.venv/bin/python orchestrator.py --project DemoApp --task 10 \
  --coder claude-cli --checker gemini

# Custom Gemini model
.venv/bin/python orchestrator.py --project DemoApp --task 10 \
  --coder gemini --coder-model google/gemini-2.5-flash
```

When `--coder`/`--checker` are omitted, the backend falls back to `implementation` in `agent_config.yml`.

> **Note:** `gemini_api_key` in `agent_config.yml` is intentionally left empty — store the key in `GOOGLE_GENERATIVE_AI_API_KEY` env var or use `opencode auth`. Never commit API keys to git.

### Resetting a failed task

If a task is stuck in `failed` or `closed` status and you want to retry it:
```bash
sqlite3 database/<Project>/tasks.db \
  "UPDATE tasks SET status='ready', attempts=0, review_notes=NULL WHERE task_number=<N>"
```

Then re-run the orchestrator normally.

### All ways to run a single task (example: task 10, project DemoApp)

**Reset before each run** (if task is already `closed` or `failed`):
```bash
sqlite3 database/DemoApp/tasks.db \
  "UPDATE tasks SET status='ready', attempts=0, review_notes=NULL WHERE task_number=10"
```

**Regular orchestrator — all backend combinations:**
```bash
# Claude subscription (no key needed)
.venv/bin/python orchestrator.py --project DemoApp --task 10 --coder claude-cli --checker claude-cli

# Gemini for both (needs GEMINI_API_KEY)
.venv/bin/python orchestrator.py --project DemoApp --task 10 --coder gemini --checker gemini

# Gemini codes, Claude reviews
.venv/bin/python orchestrator.py --project DemoApp --task 10 --coder gemini --checker claude-cli

# Claude codes, Gemini reviews
.venv/bin/python orchestrator.py --project DemoApp --task 10 --coder claude-cli --checker gemini

# Gemini with a specific model
.venv/bin/python orchestrator.py --project DemoApp --task 10 \
  --coder gemini --coder-model google/gemini-2.5-flash --checker claude-cli
```

**Agno orchestrator — all backend combinations:**
```bash
# Claude subscription (no key needed)
.venv/bin/python agno_orchestrator.py \
  --task tasks/DemoApp/10-gifloadresult-getornull.md \
  --coder claude-cli --checker claude-cli --auto

# Gemini for both (needs GOOGLE_API_KEY)
.venv/bin/python agno_orchestrator.py \
  --task tasks/DemoApp/10-gifloadresult-getornull.md \
  --coder gemini --checker gemini --auto

# Gemini codes, Claude reviews
.venv/bin/python agno_orchestrator.py \
  --task tasks/DemoApp/10-gifloadresult-getornull.md \
  --coder gemini --checker claude-cli --auto

# Claude codes, Gemini reviews
.venv/bin/python agno_orchestrator.py \
  --task tasks/DemoApp/10-gifloadresult-getornull.md \
  --coder claude-cli --checker gemini --auto
```

> Note: Agno reads `GOOGLE_API_KEY`; the regular orchestrator reads `GEMINI_API_KEY` (or `gemini_api_key` in `agent_config.yml`).

## Getting Started

```bash
uv venv
uv pip install -e ".[dev]"
.venv/bin/python seed.py --project python_fixture
.venv/bin/python orchestrator.py --project python_fixture --watch
```

To process tasks for only one project:

```bash
.venv/bin/python orchestrator.py --project python_fixture --watch
```

To process only one specific task:

```bash
.venv/bin/python orchestrator.py --task 1 --watch
```

You can combine both filters:

```bash
.venv/bin/python orchestrator.py --project DemoApp --task 7 --watch
```

In another terminal, watch execution with either:

```bash
.venv/bin/python printer.py --project python_fixture
.venv/bin/python tui.py --project python_fixture
```

## Adding A New Project

To connect a new repository to the orchestrator, add both the project repo and at least one task spec.

1. Copy or clone the target repository into `projects/<project_name>/`.
2. Ensure the project already builds or tests locally with its own commands.
4. Add one or more task files to `tasks/<project_name>/` and point them at the repo with `Project: <project_name>`.
5. Run `seed.py --project <project_name>` to load those tasks into `database/<project_name>/tasks.db`.
6. Run `orchestrator.py --project <project_name> --watch` to let the agents pick them up.

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

Recommended location for that file:

```text
tasks/my_android_app/001-fix-login-crash.md
```

Then load and run:

```bash
.venv/bin/python seed.py --project my_android_app
.venv/bin/python orchestrator.py --project my_android_app --watch
```

## How To Verify The System

Use the Python fixture first. It is the reference example for onboarding and regression testing.

```bash
.venv/bin/pytest
```

Expected result: the repository test suite passes, including the project-local integration path under `tests/python_fixture/` that seeds `tasks/python_fixture/`, writes `database/python_fixture/tasks.db`, targets `projects/python_fixture/`, and closes all 5 sample tasks with fake agents.

Live agent smoke tests require `ANTHROPIC_API_KEY`:

```bash
ANTHROPIC_API_KEY=... .venv/bin/pytest -m live
```
