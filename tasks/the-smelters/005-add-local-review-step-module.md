Project: the-smelters

# Add local reviewer step module for post-PR analysis

## Big picture

After the PR exists, the pipeline needs a local reviewer run (Claude or opencode/Gemini) to produce actionable findings. Isolating this in its own module keeps orchestration logic simple and makes backend-specific behavior testable.

## Integration points

- New file: `agno_tools/pr_reviewer_step.py`
- Existing reviewer prompt patterns in `agents/reviewer.py`
- Smelters workflow chain after PR creation

## Scope

- Implement reviewer step module with:
  - backend selector (`claude` / `gemini`)
  - normalized review result payload
  - compact markdown summary generator
  - explicit reviewer input context containing task file path and task markdown body
- Keep logic read-only with respect to project source.

## Acceptance criteria

- Reviewer step runs locally using selected backend.
- Reviewer always receives the original task context so findings are evaluated against expected scope.
- Output contains structured verdict/findings summary consumable by comment publisher.
- Failures are captured and surfaced in a machine-usable form.

## Unit verification

- Add tests for:
  - reviewer success response parsing
  - malformed reviewer output handling
  - backend selection branch behavior
  - reviewer prompt/context builder includes task spec path and task markdown
- Run: `python -m pytest tests/ -k "pr reviewer step" -v`

## Human verification

1. Run with Claude backend and confirm reviewer output is captured with task context visible in prompt construction logs/debug dumps.
2. Run with Gemini/opencode backend and confirm same normalized shape.
3. Confirm output text is readable and concise for PR consumption.

## Out of scope

- Posting comments to GitHub
- Auto-fix loop after review
