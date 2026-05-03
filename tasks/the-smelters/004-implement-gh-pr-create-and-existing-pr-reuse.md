Project: the-smelters

# Implement PR creation command and existing-PR reuse

## Big picture

The pipeline must reliably end with a PR to review. Creating duplicates each run makes noise, while failing on already-open branches blocks automation. This task implements robust PR resolution for stable repeated runs.

## Integration points

- `agno_tools/pr_create_step.py`
- `gh` CLI usage from orchestrator runtime
- Step output consumed by reviewer comment stage

## Scope

- Execute `gh pr create` with resolved config.
- Handle "PR already exists" path by resolving and returning the existing PR.
- Normalize return payload:
  - `pr_number`
  - `pr_url`
  - `created_new` boolean
- Keep command construction readable and testable.

## Acceptance criteria

- First run creates PR and returns URL/number.
- Re-run on same branch reuses existing PR instead of failing.
- Failure messages include root cause and next action.

## Unit verification

- Mock command runner and cover:
  - create success
  - create returns already-exists signal + resolve success
  - command failure (auth/network/repo not found)
- Run: `python -m pytest tests/ -k "pr create and gh" -v`

## Human verification

1. Run smelters flow with valid args and verify PR is created.
2. Re-run same flow and verify same PR is reused.
3. Temporarily invalidate token and verify error output is actionable.

## Out of scope

- Reviewer analysis
- PR comment publishing
