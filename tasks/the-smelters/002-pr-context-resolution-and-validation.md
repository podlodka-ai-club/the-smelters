Project: the-smelters

# Resolve PR context and normalize runtime config

## Big picture

PR creation and review comment steps should not parse raw CLI values repeatedly. A normalized config object prevents drift, reduces bugs, and makes step modules easier to read and test.

## Integration points

- `agno_orchestrator.py` smelters-mode setup path
- Shared helper functions for config normalization
- Data passed into new PR creation and reviewer steps

## Scope

- Introduce a small typed config payload for PR/review context.
- Normalize and validate:
  - `repo` format (`owner/name`)
  - base/head branch values
  - token env variable lookup
  - optional PR title/body file handling
  - reviewer task-context payload source (task path + task markdown text)
- Emit explicit errors with actionable remediation.

## Acceptance criteria

- Config resolution happens once before workflow execution.
- Downstream steps receive a clean payload and do not re-validate raw CLI input.
- Reviewer receives normalized task context in the same payload shape on every run.
- Error messages identify exactly which field is invalid.

## Unit verification

- Add focused tests for config resolver:
  - valid repo parsing
  - invalid repo format
  - missing token env var
  - optional body file missing/unreadable
  - task context extraction from task file path/content
- Run: `python -m pytest tests/ -k "config and pr context" -v`

## Human verification

1. Pass malformed `--repo` and verify run exits with specific format guidance.
2. Pass missing `--github-token-env` value and verify run exits early with remediation.
3. Provide valid inputs and verify normalized values appear in debug/startup output.

## Out of scope

- GitHub API calls
- PR creation command execution
