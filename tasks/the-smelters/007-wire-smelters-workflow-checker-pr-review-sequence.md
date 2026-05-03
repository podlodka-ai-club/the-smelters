Project: the-smelters

# Wire workflow sequence: checker -> create PR -> review -> comment

## Big picture

The value of the new modules appears only when orchestration order is correct. This task integrates all new steps in the smelters flow with clear conditional behavior and minimal changes to existing loop logic.

## Integration points

- `agno_orchestrator.py`
- `build_smelters_workflow(...)`
- New modules:
  - `agno_tools/pr_create_step.py`
  - `agno_tools/pr_reviewer_step.py`

## Scope

- Keep `CoderCheckerLoop` behavior unchanged.
- Add post-loop chain only when checker status is `passed`:
  1. Create/reuse PR
  2. Build reviewer input with task context (task path + markdown body)
  3. Run local reviewer
  4. Publish review comment
- Ensure class-mode flow remains untouched.

## Acceptance criteria

- Checker failure path ends without PR/reviewer execution.
- Checker success path executes new chain in deterministic order.
- Reviewer stage receives the original task context before execution.
- Runtime output clearly shows which stage succeeded/failed.

## Unit verification

- Add integration-style orchestrator tests for:
  - checker failed -> no PR creation
  - checker passed -> PR+review chain executes
  - checker passed -> reviewer is called with task-context fields populated
  - PR creation fails -> reviewer/comment stage handling follows defined behavior
- Run: `python -m pytest tests/ -k "smelters workflow and pr" -v`

## Human verification

1. Simulate checker fail and verify workflow stops before PR steps.
2. Simulate checker pass and verify all new stages run in order.
3. Verify logs are readable and each stage has explicit status lines.

## Out of scope

- New retry strategy for reviewer findings
- Non-smelters pipeline integration
