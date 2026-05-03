from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TASK_CONTEXT_MODES = {"inline", "path"}


def validate_smelters_pr_context(args: argparse.Namespace) -> None:
    """Validate CLI inputs required for smelters PR/review flow."""
    repo = (args.repo or "").strip()
    if not repo:
        sys.exit(
            "ERROR: --repo is required in smelters mode.\n"
            "  Expected format: --repo owner/name"
        )
    if not _REPO_SLUG_RE.match(repo):
        sys.exit(
            f"ERROR: invalid --repo value: {args.repo!r}\n"
            "  Expected format: owner/name"
        )

    token_env_name = (args.github_token_env or "").strip()
    if not token_env_name:
        sys.exit(
            "ERROR: --github-token-env cannot be empty.\n"
            "  Example: --github-token-env GITHUB_TOKEN"
        )
    if not os.environ.get(token_env_name):
        sys.exit(
            f"ERROR: {token_env_name} is not set (required for PR creation/review publishing).\n"
            f"  Export it first, e.g. `export {token_env_name}=<token>`."
        )

    if args.pr_body_file:
        body_path = Path(args.pr_body_file)
        if not body_path.exists() or not body_path.is_file():
            sys.exit(
                f"ERROR: --pr-body-file was provided but file was not found: {body_path}"
            )

    task_context_mode = (args.task_context_mode or "").strip()
    if task_context_mode not in _TASK_CONTEXT_MODES:
        allowed = ", ".join(sorted(_TASK_CONTEXT_MODES))
        sys.exit(
            f"ERROR: unsupported --task-context-mode value: {args.task_context_mode!r}\n"
            f"  Supported values: {allowed}"
        )
