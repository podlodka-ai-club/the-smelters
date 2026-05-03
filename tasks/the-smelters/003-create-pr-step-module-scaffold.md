Project: the-smelters

# Add dedicated PR creation step module scaffold

## Big picture

You requested PR creation as a separate step/file before reviewer execution. This task creates that isolated module so orchestration logic stays readable and each responsibility has one home.

## Integration points

- New file: `agno_tools/pr_create_step.py`
- Step creation/import in `agno_orchestrator.py`
- Smelters workflow chain after checker success

## Scope

- Create a standalone module with:
  - typed request/response payloads
  - public factory/function used by orchestrator
  - clear internal function boundaries
- Stub command execution path and response shaping.
- Add docstrings and naming aligned with repository style.

## Acceptance criteria

- Module compiles and imports cleanly.
- Orchestrator can construct the step without executing GitHub commands yet.
- Step output contract includes `pr_number` and `pr_url` fields.

## Unit verification

- Add tests that instantiate the step and assert payload structure.
- Verify error object format for placeholder failure paths.
- Run: `python -m pytest tests/ -k "pr_create_step and scaffold" -v`

## Human verification

1. Open `agno_tools/pr_create_step.py` and confirm it is easy to scan.
2. Verify function names clearly indicate intent.
3. Confirm module is imported by orchestrator without circular imports.

## Out of scope

- Actual `gh pr create` calls
- Existing PR reuse logic
