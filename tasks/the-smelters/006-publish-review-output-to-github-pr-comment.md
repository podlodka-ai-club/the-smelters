Project: the-smelters

# Publish reviewer findings to GitHub PR comments

## Big picture

Local reviewer output has limited value unless it appears where developers collaborate: the PR. This task bridges local analysis and team workflow by posting a clear review comment to the created PR.

## Integration points

- `agno_tools/pr_reviewer_step.py`
- GitHub PR target from `pr_create_step` output
- `gh api` comment publishing path

## Scope

- Implement GitHub comment publishing helper:
  - create comment with structured markdown
  - optional idempotent update strategy (stable marker)
  - include reviewer verdict summary and key findings
- Ensure token env from CLI config is used consistently.

## Acceptance criteria

- On successful reviewer run, PR receives a readable comment.
- Publishing errors do not crash unrelated orchestration steps; they are logged clearly.
- Comment content is concise, scannable, and includes next actions.

## Unit verification

- Mock `gh api` calls and cover:
  - comment create success
  - comment update success (if marker strategy used)
  - auth/permission failure path
- Run: `python -m pytest tests/ -k "github comment and reviewer" -v`

## Human verification

1. Trigger run and confirm comment appears in target PR.
2. Trigger second run and verify duplicate-comment behavior is acceptable (create new or update existing by design).
3. Confirm comments include verdict + top findings and are easy for reviewers to consume.

## Out of scope

- Branch protection or merge gating rules
- Automatic code fixes based on findings
