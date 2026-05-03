Project: the-smelters

# Add comprehensive tests for PR creation and reviewer flow

## Big picture

Without tests, orchestration changes can silently regress and break automation. This task provides confidence that the new PR+review chain works across success and failure states.

## Integration points

- `tests/` suite for orchestrator and step modules
- New module tests for:
  - `agno_tools/pr_create_step.py`
  - `agno_tools/pr_reviewer_step.py`
- Existing orchestrator tests

## Scope

- Add/expand tests for:
  - CLI argument/validation branches
  - PR create success and existing PR reuse
  - reviewer parsing and comment publishing
  - checker-pass conditional wiring
- Use mocks/fakes for external command execution.

## Acceptance criteria

- New tests are deterministic and do not require real GitHub/network calls.
- Coverage includes happy paths plus key error paths.
- Existing unrelated tests remain green.

## Unit verification

- Run targeted: `python -m pytest tests/ -k "agno or pr_create or pr_reviewer" -v`
- Run full suite: `python -m pytest tests/ -v`

## Human verification

1. Inspect tests and confirm each maps to a user-visible behavior.
2. Confirm test names are descriptive and failure messages are understandable.
3. Confirm no flaky timing/network dependencies were introduced.

## Out of scope

- UI/manual testing automation
- Performance benchmarking
