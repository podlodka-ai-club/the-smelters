Project: the-smelters

# Document the new post-checker PR and review flow

## Big picture

Developers and operators need accurate docs to run and troubleshoot the updated pipeline. Documentation drift causes failed runs and unclear ownership.

## Integration points

- `PROJECT.md`
- `README.md`
- CLI examples and flow diagrams/text sections

## Scope

- Update flow description to include:
  - PR creation step before reviewer
  - local reviewer execution backend options
  - PR comment publishing behavior
- Add end-to-end command examples with new CLI args.
- Document required GitHub token env contract.

## Acceptance criteria

- Docs reflect actual runtime behavior and argument names.
- Setup instructions are enough for a new contributor to run the flow.
- No contradictory statements remain in old sections.

## Unit verification

- N/A (documentation task)
- Optional consistency check: run `rg` for outdated flow strings and remove mismatches.

## Human verification

1. Follow README commands in a dry run and confirm argument names exist.
2. Verify PROJECT and README describe the same ordered flow.
3. Confirm docs explain where PR URL and reviewer comments appear.

## Out of scope

- Product-level roadmap changes outside this feature
