"""Resolve GitHub credentials: env var (e.g. ``GITHUB_TOKEN``) or ``gh auth token``."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def fill_github_token_from_cli(token_env_name: str) -> bool:
    """Ensure ``os.environ[token_env_name]`` is set if possible.

    If the variable is already non-empty, returns True immediately.
    Otherwise, when ``gh`` is on PATH, runs ``gh auth token`` and copies the result into the env var.

    Returns True if the env var is non-empty after this call.
    """
    if (os.environ.get(token_env_name) or "").strip():
        return True
    if not shutil.which("gh"):
        return False
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    token = (result.stdout or "").strip()
    if not token:
        return False
    os.environ[token_env_name] = token
    return True


def missing_github_token_message(token_env_name: str) -> str:
    """Human-readable explanation when no token is available (API / publishing tools)."""
    if not shutil.which("gh"):
        return (
            f"{token_env_name} is not set and the GitHub CLI (`gh`) is not on PATH. "
            f"Export {token_env_name}, or install GitHub CLI and run `gh auth login`."
        )
    try:
        status = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        status = None
    diag = ""
    if status is not None:
        chunk = (status.stderr or status.stdout or "").strip()
        if chunk:
            diag = f" ({chunk[:600]}{'…' if len(chunk) > 600 else ''})"
    return (
        f"{token_env_name} is not set and `gh auth token` did not return a credential.{diag} "
        f"Run `gh auth login` or export {token_env_name}."
    )


def ensure_github_token_or_exit(token_env_name: str) -> None:
    """Used at Smelters startup: require GitHub auth for PR/review steps."""
    if fill_github_token_from_cli(token_env_name):
        return
    sys.exit(
        "ERROR: GitHub authentication required for PR create/review publishing.\n"
        f"  {missing_github_token_message(token_env_name)}"
    )
