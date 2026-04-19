# Repository Guidelines

## Project Structure & Module Organization

This repository is currently documentation-first. The root contains `docs/` and contributor guidance files. Active project material lives under `docs/superpowers/`:

- `docs/superpowers/specs/` stores design specs such as `2026-04-18-multi-agent-dev-assistant-design.md`.
- `docs/superpowers/plans/` stores implementation plans paired to those specs.

Use date-prefixed filenames in `YYYY-MM-DD-topic.md` form so specs and plans sort chronologically. Keep related spec and plan names aligned.

## Build, Test, and Development Commands

No build system, package manifest, or automated test runner is configured in this checkout yet. Use lightweight shell checks when editing docs:

- `find docs -maxdepth 3 -type f | sort` lists tracked documentation files.
- `sed -n '1,160p' docs/superpowers/specs/<file>.md` reviews a spec without opening an editor.
- `sed -n '1,160p' docs/superpowers/plans/<file>.md` reviews the paired plan.

If you add tooling later, document the exact command here and keep it reproducible from the repository root.

## Coding Style & Naming Conventions

Write Markdown with short sections, direct prose, and fenced code blocks for commands or examples. Prefer concise headings and stable relative paths. Keep filenames lowercase with hyphen-separated topics, and preserve the existing date prefix pattern for new planning documents.

Avoid committing editor or OS artifacts such as `.DS_Store`. When expanding the repo beyond docs, place source and tests in clearly named top-level directories instead of mixing them into `docs/`.

## Testing Guidelines

There is no automated coverage target yet. For documentation changes, verify:

- links and paths resolve from the repository root,
- spec and plan filenames match their subject,
- new content is internally consistent and free of placeholders like `TODO` or `TBD`.

Treat a careful read-through as the minimum validation step before submitting changes.

## Commit & Pull Request Guidelines

This directory is not currently a Git working tree, so there is no local history to infer conventions from. Use short, imperative commit subjects in a Conventional Commit style when version control is enabled, for example `docs: add contributor guide` or `docs: refine assistant plan`.

Pull requests should explain the affected document set, summarize why the change is needed, and call out renamed or newly added files. Include screenshots only when a rendered view or formatting change needs visual confirmation.
