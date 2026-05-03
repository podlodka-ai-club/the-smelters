from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional

from src.smelters_review_context import SmeltersReviewContext


@dataclass(frozen=True)
class PrCreateRequest:
    repo: str
    base_branch: str
    head_branch: str | None
    title: str | None
    body_file: str | None


@dataclass(frozen=True)
class PrCreateResult:
    ok: bool
    pr_number: int | None
    pr_url: str | None
    created_new: bool
    error: str | None = None


@dataclass(frozen=True)
class StepOutputLike:
    content: str


@dataclass(frozen=True)
class GhCommandResult:
    returncode: int
    stdout: str
    stderr: str


def _format_gh_error(prefix: str, command_result: GhCommandResult) -> str:
    message = (command_result.stderr or command_result.stdout).strip() or "unknown error"
    return f"{prefix}: {message}"


def build_pr_create_request(context: SmeltersReviewContext) -> PrCreateRequest:
    return PrCreateRequest(
        repo=context.repo,
        base_branch=context.base_branch,
        head_branch=context.head_branch,
        title=context.pr_title,
        body_file=context.pr_body_file,
    )


def _run_gh_command(args: list[str]) -> GhCommandResult:
    completed = subprocess.run(
        args,
        text=True,
        capture_output=True,
        check=False,
    )
    return GhCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _run_git(args: list[str], *, cwd: str) -> GhCommandResult:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    completed = subprocess.run(
        args,
        cwd=cwd,
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


def _path_under_scope(path: str, scope: str) -> bool:
    norm = path.replace("\\", "/").strip()
    scope_n = scope.strip().strip("/")
    return norm == scope_n or norm.startswith(f"{scope_n}/")


def _has_scoped_commits_since_base(repo_root: str, scope: str, base_branch: str) -> bool:
    log_r = _run_git(
        ["git", "log", f"{base_branch}..HEAD", "--format=%H", "-n", "1", "--", f"{scope}/"],
        cwd=repo_root,
    )
    if log_r.returncode != 0:
        return False
    return bool((log_r.stdout or "").strip())


def _smelters_branch_name(scope: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", scope).strip("-").lower()[:48] or "project"
    return f"smelters/{slug}-{uuid.uuid4().hex[:8]}"


def _current_branch(repo_root: str) -> str | None:
    r = _run_git(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)
    if r.returncode != 0:
        return None
    name = (r.stdout or "").strip()
    return name or None


def _branch_exists(repo_root: str, name: str) -> bool:
    r = _run_git(["git", "rev-parse", "--verify", f"refs/heads/{name}"], cwd=repo_root)
    return r.returncode == 0


def _checkout_or_create_branch(repo_root: str, name: str) -> GhCommandResult:
    if _branch_exists(repo_root, name):
        return _run_git(["git", "checkout", "-q", name], cwd=repo_root)
    return _run_git(["git", "checkout", "-q", "-b", name], cwd=repo_root)


def prepare_scoped_git_for_pr(context: SmeltersReviewContext) -> tuple[bool, str | None, str | None]:
    """Stage, commit, and push only paths under ``context.project_scope_posix``.

    Returns ``(ok, error_message, head_branch_for_gh)``. ``head_branch_for_gh`` is the local
    branch name to pass to ``gh pr create --head`` after a successful push.
    """
    scope = context.project_scope_posix.strip().strip("/")
    root_r = _run_git(["git", "rev-parse", "--show-toplevel"], cwd=os.getcwd())
    if root_r.returncode != 0:
        return False, (root_r.stderr or root_r.stdout or "git rev-parse failed").strip(), None
    repo_root = (root_r.stdout or "").strip()

    # Intentionally no "clean tree outside scope" requirement: only paths under ``scope/``
    # are staged and committed, so orchestration or docs may remain dirty locally.

    reset = _run_git(["git", "reset", "-q", "HEAD"], cwd=repo_root)
    if reset.returncode != 0:
        return False, f"git reset failed: {(reset.stderr or reset.stdout).strip()}", None

    current = _current_branch(repo_root)
    if current is None:
        return False, "Could not read current git branch.", None

    if context.head_branch:
        co = _checkout_or_create_branch(repo_root, context.head_branch)
        if co.returncode != 0:
            return False, f"Could not checkout branch {context.head_branch!r}: {(co.stderr or co.stdout).strip()}", None
    elif current in {"main", "master"}:
        new_branch = _smelters_branch_name(scope)
        co = _run_git(["git", "checkout", "-q", "-b", new_branch], cwd=repo_root)
        if co.returncode != 0:
            return False, f"Could not create branch {new_branch!r}: {(co.stderr or co.stdout).strip()}", None

    add = _run_git(["git", "add", "--", f"{scope}/"], cwd=repo_root)
    if add.returncode != 0:
        return False, f"git add failed: {(add.stderr or add.stdout).strip()}", None

    names = _run_git(["git", "diff", "--cached", "--name-only"], cwd=repo_root)
    if names.returncode != 0:
        return False, f"git diff --cached failed: {(names.stderr or names.stdout).strip()}", None
    staged = [ln.strip() for ln in (names.stdout or "").splitlines() if ln.strip()]
    for path in staged:
        if not _path_under_scope(path, scope):
            return (
                False,
                f"Refusing PR: after staging only {scope}/, unexpected path in index: {path}",
                None,
            )

    has_staged = bool(staged)
    if not has_staged and not _has_scoped_commits_since_base(repo_root, scope, context.base_branch):
        return (
            False,
            f"No changes to publish under {scope}/ (nothing staged and no commits on HEAD vs "
            f"{context.base_branch} touching that tree).",
            None,
        )

    if has_staged:
        msg = (context.pr_title or f"feat({scope}): smelters update").strip()
        commit = _run_git(["git", "commit", "-m", msg], cwd=repo_root)
        if commit.returncode != 0:
            return False, f"git commit failed: {(commit.stderr or commit.stdout).strip()}", None

    push = _run_git(["git", "push", "-u", "origin", "HEAD"], cwd=repo_root)
    if push.returncode != 0:
        return False, f"git push failed: {(push.stderr or push.stdout).strip()}", None

    head = _current_branch(repo_root)
    if not head or head == "HEAD":
        return False, "Detached HEAD after push; cannot determine branch for gh pr create.", None
    return True, None, head


def _extract_pr_number_from_url(url: str) -> int | None:
    tail = url.rstrip("/").split("/")[-1]
    return int(tail) if tail.isdigit() else None


def create_or_reuse_pull_request(
    request: PrCreateRequest,
    *,
    run_command: Callable[[list[str]], GhCommandResult] = _run_gh_command,
) -> PrCreateResult:
    """Create a PR or resolve an already-open PR for the branch."""
    create_cmd = [
        "gh",
        "pr",
        "create",
        "--repo",
        request.repo,
        "--base",
        request.base_branch,
    ]
    if request.head_branch:
        create_cmd += ["--head", request.head_branch]
    if request.title:
        create_cmd += ["--title", request.title]
    if request.body_file:
        create_cmd += ["--body-file", request.body_file]
    else:
        create_cmd += ["--body", "Automated PR created by smelters orchestrator."]

    created = run_command(create_cmd)
    if created.returncode == 0:
        pr_url = created.stdout.strip().splitlines()[-1].strip()
        return PrCreateResult(
            ok=True,
            pr_number=_extract_pr_number_from_url(pr_url),
            pr_url=pr_url,
            created_new=True,
        )

    combined_err = f"{created.stdout}\n{created.stderr}".lower()
    if "already exists" not in combined_err:
        return PrCreateResult(
            ok=False,
            pr_number=None,
            pr_url=None,
            created_new=False,
            error=_format_gh_error("gh pr create failed", created),
        )

    list_cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        request.repo,
        "--state",
        "open",
        "--json",
        "number,url,headRefName",
    ]
    if request.head_branch:
        list_cmd += ["--head", request.head_branch]
    listed = run_command(list_cmd)
    if listed.returncode != 0:
        return PrCreateResult(
            ok=False,
            pr_number=None,
            pr_url=None,
            created_new=False,
            error=_format_gh_error("gh pr list failed while resolving existing PR", listed),
        )
    try:
        entries = json.loads(listed.stdout or "[]")
    except json.JSONDecodeError:
        entries = []
    if not isinstance(entries, list) or not entries:
        return PrCreateResult(
            ok=False,
            pr_number=None,
            pr_url=None,
            created_new=False,
            error="PR already exists but could not resolve existing PR URL/number.",
        )
    first = entries[0] or {}
    return PrCreateResult(
        ok=True,
        pr_number=first.get("number"),
        pr_url=first.get("url"),
        created_new=False,
    )


def make_pr_create_step(context: SmeltersReviewContext):
    base_request = build_pr_create_request(context)

    def _pr_create_step(step_input: Any, session_state: Optional[dict[str, Any]] = None):
        _ = step_input
        prep_ok, prep_err, head_branch = prepare_scoped_git_for_pr(context)
        if not prep_ok:
            payload = {
                "ok": False,
                "pr_number": None,
                "pr_url": None,
                "created_new": False,
                "error": prep_err,
                "project_scope_posix": context.project_scope_posix,
                "git_prepare_ok": False,
            }
            if session_state is not None:
                session_state["pr_create_result"] = payload.copy()
            return StepOutputLike(content=json.dumps(payload))

        gh_request = replace(base_request, head_branch=head_branch)
        result = create_or_reuse_pull_request(gh_request)
        payload = {
            "ok": result.ok,
            "pr_number": result.pr_number,
            "pr_url": result.pr_url,
            "created_new": result.created_new,
            "error": result.error,
            "project_scope_posix": context.project_scope_posix,
            "git_prepare_ok": True,
            "head_branch": head_branch,
        }
        if session_state is not None:
            session_state["pr_create_result"] = payload.copy()
        return StepOutputLike(content=json.dumps(payload))

    _pr_create_step.__name__ = "pr_create_step"
    return _pr_create_step
