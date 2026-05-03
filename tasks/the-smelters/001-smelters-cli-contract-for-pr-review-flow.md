Project: the-smelters

# Define CLI contract for post-checker PR+review flow

## Big picture

The smelters pipeline currently ends after checker success. To make outcomes reviewable on GitHub, the orchestrator must know where to create a PR and where to post review feedback. This task establishes a clear CLI interface so all downstream steps can rely on validated inputs.

## Integration points

- `agno_orchestrator.py` argument parser
- Smelters-mode runtime validation and startup summary output
- Existing workflow builder for `build_smelters_workflow(...)`

## Scope

- Add CLI args for PR creation and review publishing:
  - `--repo`
  - `--base-branch` (default `main`)
  - `--head-branch` (optional)
  - `--pr-title` (optional)
  - `--pr-body-file` (optional)
  - `--github-token-env` (default `GITHUB_TOKEN`)
  - `--task-context-mode` (e.g. `path` or `inline`) to control how task context is passed to reviewer
- Add clear validation errors when required combinations are missing in smelters mode.
- Keep class-mode behavior unchanged.

## Acceptance criteria

- Smelters mode fails fast with readable messages when required PR context is missing.
- Smelters mode defines and validates a reviewer-task-context strategy.
- CLI help text explains each new flag in plain language.
- Existing flags and defaults continue to work.

## Unit verification

- Add/update tests for parser and validation branches:
  - valid smelters args path
  - missing `--repo` path
  - invalid/missing token env path
  - class-mode unaffected path
- Run: `python -m pytest tests/ -k "agno and cli" -v`

## Human verification

1. Run `python agno_orchestrator.py --help` and confirm new flags are documented.
2. Run smelters mode without `--repo` and verify actionable error text.
3. Run with full args and verify startup summary prints parsed PR/review config including task-context mode.

## Out of scope

- Creating PRs
- Running reviewer
- Posting comments
