from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Callable

from src.github_auth import fill_github_token_from_cli, missing_github_token_message


REVIEW_COMMENT_MARKER = "<!-- smelters-review-comment -->"


@dataclass(frozen=True)
class GhCommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class CommentPublishResult:
    ok: bool
    comment_id: int | None
    action: str
    error: str | None = None


def _run_gh_command(args: list[str], env: dict[str, str] | None = None) -> GhCommandResult:
    completed = subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    return GhCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _command_error(result: GhCommandResult, fallback: str) -> str:
    return (result.stderr or result.stdout).strip() or fallback


def _with_marker(body: str) -> str:
    return f"{REVIEW_COMMENT_MARKER}\n{body}"


def publish_review_comment(
    *,
    repo: str,
    pr_number: int,
    body: str,
    token_env_name: str,
    run_command: Callable[[list[str], dict[str, str] | None], GhCommandResult] = _run_gh_command,
) -> CommentPublishResult:
    fill_github_token_from_cli(token_env_name)
    token = os.environ.get(token_env_name, "")
    if not token:
        return CommentPublishResult(
            ok=False,
            comment_id=None,
            action="none",
            error=missing_github_token_message(token_env_name),
        )
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    marked_body = _with_marker(body)

    list_cmd = [
        "gh",
        "api",
        f"repos/{repo}/issues/{pr_number}/comments",
    ]
    listed = run_command(list_cmd, env)
    if listed.returncode != 0:
        return CommentPublishResult(
            ok=False,
            comment_id=None,
            action="none",
            error=_command_error(listed, "failed to list comments"),
        )
    try:
        comments = json.loads(listed.stdout or "[]")
    except json.JSONDecodeError:
        comments = []

    existing_id = None
    if isinstance(comments, list):
        for comment in comments:
            if isinstance(comment, dict) and REVIEW_COMMENT_MARKER in str(comment.get("body", "")):
                existing_id = comment.get("id")
                break

    if existing_id:
        patch_cmd = [
            "gh",
            "api",
            f"repos/{repo}/issues/comments/{existing_id}",
            "-X",
            "PATCH",
            "-f",
            f"body={marked_body}",
        ]
        patched = run_command(patch_cmd, env)
        if patched.returncode != 0:
            return CommentPublishResult(
                ok=False,
                comment_id=existing_id,
                action="update",
                error=_command_error(patched, "failed to update comment"),
            )
        return CommentPublishResult(ok=True, comment_id=existing_id, action="update")

    create_cmd = [
        "gh",
        "api",
        f"repos/{repo}/issues/{pr_number}/comments",
        "-X",
        "POST",
        "-f",
        f"body={marked_body}",
    ]
    created = run_command(create_cmd, env)
    if created.returncode != 0:
        return CommentPublishResult(
            ok=False,
            comment_id=None,
            action="create",
            error=_command_error(created, "failed to create comment"),
        )
    try:
        payload = json.loads(created.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    return CommentPublishResult(
        ok=True,
        comment_id=payload.get("id"),
        action="create",
    )
