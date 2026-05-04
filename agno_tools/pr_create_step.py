from __future__ import annotations

import json
import os
import re
import subprocess
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


def _repo_relative_paths_with_local_changes(repo_root: str) -> set[str]:
    """Paths (POSIX, relative to repo) that differ from HEAD or are untracked (excluding ignored)."""
    out: set[str] = set()
    for cmd in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
    ):
        r = _run_git(cmd, cwd=repo_root)
        if r.returncode == 0:
            for ln in (r.stdout or "").splitlines():
                p = ln.strip().replace("\\", "/")
                if p:
                    out.add(p)
    unt = _run_git(["git", "ls-files", "-o", "--exclude-standard"], cwd=repo_root)
    if unt.returncode == 0:
        for ln in (unt.stdout or "").splitlines():
            p = ln.strip().replace("\\", "/")
            if p:
                out.add(p)
    return out


def _worktree_dirty_outside_scope(repo_root: str, scope: str) -> list[str]:
    """Return paths outside ``scope/`` that have local changes; empty if clean outside scope."""
    scope_n = scope.strip().strip("/")
    bad: list[str] = []
    for p in sorted(_repo_relative_paths_with_local_changes(repo_root)):
        if not _path_under_scope(p, scope_n):
            bad.append(p)
    return bad


_MAX_TASK_BRANCH_SLUG = 100

_MAIN_BRANCH = "main"


def _branch_name_from_task_path(task_path: str) -> str:
    """Git-safe branch name from task file path (e.g. tasks/DemoApp/6-foo.md)."""
    raw = (task_path or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("empty task_path")
    stem = raw[:-3] if raw.lower().endswith(".md") else raw
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    if not slug:
        slug = "task"
    slug = slug[:_MAX_TASK_BRANCH_SLUG]
    return f"smelters/{slug}"


def _remote_head_branch_exists(repo_root: str, remote: str, branch: str) -> bool:
    r = _run_git(["git", "ls-remote", "--heads", remote, branch], cwd=repo_root)
    if r.returncode != 0:
        return False
    return bool((r.stdout or "").strip())


def _has_scoped_commits_between(repo_root: str, scope: str, base_ref: str, head_ref: str) -> bool:
    log_r = _run_git(
        ["git", "log", f"{base_ref}..{head_ref}", "--format=%H", "-n", "1", "--", f"{scope}/"],
        cwd=repo_root,
    )
    if log_r.returncode != 0:
        return False
    return bool((log_r.stdout or "").strip())


def _has_scoped_commits_since_base(repo_root: str, scope: str, base_branch: str) -> bool:
    return _has_scoped_commits_between(repo_root, scope, base_branch, "HEAD")


def _format_dirty_outside_scope_error(paths: list[str]) -> str:
    cap = 12
    shown = paths[:cap]
    extra = f" (+{len(paths) - cap} more)" if len(paths) > cap else ""
    joined = "\n  ".join(shown)
    return (
        "Refusing PR git prep: the working tree has local changes outside the Smelters project scope. "
        "Commit, stash, or discard them before re-running (only paths under the project directory may be dirty):\n  "
        f"{joined}{extra}"
    )


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


def _stage_scope_and_list_cached(repo_root: str, scope: str) -> tuple[bool, str | None, list[str]]:
    add = _run_git(["git", "add", "--", f"{scope}/"], cwd=repo_root)
    if add.returncode != 0:
        return False, f"git add failed: {(add.stderr or add.stdout).strip()}", []
    names = _run_git(["git", "diff", "--cached", "--name-only"], cwd=repo_root)
    if names.returncode != 0:
        return False, f"git diff --cached failed: {(names.stderr or names.stdout).strip()}", []
    staged = [ln.strip() for ln in (names.stdout or "").splitlines() if ln.strip()]
    for path in staged:
        if not _path_under_scope(path, scope):
            return (
                False,
                f"Refusing PR: after staging only {scope}/, unexpected path in index: {path}",
                [],
            )
    return True, None, staged


def prepare_scoped_git_for_pr(context: SmeltersReviewContext) -> tuple[bool, str | None, str | None]:
    """Stage, commit, and push only paths under ``context.project_scope_posix``.

    Default (no ``--head-branch``): require a clean worktree outside the project scope, then
    ``fetch``/``checkout``/``pull --ff-only`` ``main``, create a task-named branch from ``main``,
    replay scoped work from the pre-run HEAD, commit, and push.

    Returns ``(ok, error_message, head_branch_for_gh)``. ``head_branch_for_gh`` is the local
    branch name to pass to ``gh pr create --head`` after a successful push.
    """
    scope = context.project_scope_posix.strip().strip("/")
    root_r = _run_git(["git", "rev-parse", "--show-toplevel"], cwd=os.getcwd())
    if root_r.returncode != 0:
        return False, (root_r.stderr or root_r.stdout or "git rev-parse failed").strip(), None
    repo_root = (root_r.stdout or "").strip()

    reset = _run_git(["git", "reset", "-q", "HEAD"], cwd=repo_root)
    if reset.returncode != 0:
        return False, f"git reset failed: {(reset.stderr or reset.stdout).strip()}", None

    current = _current_branch(repo_root)
    if current is None:
        return False, "Could not read current git branch.", None

    outside = _worktree_dirty_outside_scope(repo_root, scope)
    if outside:
        return False, _format_dirty_outside_scope_error(outside), None

    if context.head_branch:
        co = _checkout_or_create_branch(repo_root, context.head_branch)
        if co.returncode != 0:
            return False, f"Could not checkout branch {context.head_branch!r}: {(co.stderr or co.stdout).strip()}", None
        ok_stage, err_stage, staged = _stage_scope_and_list_cached(repo_root, scope)
        if not ok_stage:
            return False, err_stage, None
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

    if context.base_branch.strip() != _MAIN_BRANCH:
        return (
            False,
            "Smelters default PR git prep always branches from local `main` and targets `--base-branch main`. "
            "Pass `--base-branch main` (or omit it), or set `--head-branch` to manage the git branch yourself.",
            None,
        )

    head_r = _run_git(["git", "rev-parse", "HEAD"], cwd=repo_root)
    if head_r.returncode != 0:
        return False, (head_r.stderr or head_r.stdout or "git rev-parse HEAD failed").strip(), None
    source_head = (head_r.stdout or "").strip()

    try:
        task_branch = _branch_name_from_task_path(context.task_path)
    except ValueError as exc:
        return False, str(exc), None

    if _branch_exists(repo_root, task_branch):
        return (
            False,
            f"Branch {task_branch!r} already exists locally. Delete or rename it, or pass --head-branch.",
            None,
        )
    if _remote_head_branch_exists(repo_root, "origin", task_branch):
        return (
            False,
            f"Branch {task_branch!r} already exists on origin. Remove it on the remote or pass --head-branch.",
            None,
        )

    ok_stage, err_stage, staged = _stage_scope_and_list_cached(repo_root, scope)
    if not ok_stage:
        return False, err_stage, None
    has_staged = bool(staged)
    has_scoped_commits = _has_scoped_commits_between(repo_root, scope, _MAIN_BRANCH, source_head)
    if not has_staged and not has_scoped_commits:
        return (
            False,
            f"No changes to publish under {scope}/ (nothing staged and no commits on the previous HEAD vs "
            f"{_MAIN_BRANCH} touching that tree).",
            None,
        )

    stash_r = _run_git(
        ["git", "stash", "push", "-u", "-m", "smelters-scoped-pr", "--", f"{scope}/"],
        cwd=repo_root,
    )
    combined_stash = f"{stash_r.stderr or ''}\n{stash_r.stdout or ''}"
    stash_created: bool
    if stash_r.returncode == 0:
        stash_created = True
    elif "No local changes to save" in combined_stash:
        stash_created = False
    else:
        return False, f"git stash failed: {combined_stash.strip()}", None

    fetch = _run_git(["git", "fetch", "origin", _MAIN_BRANCH], cwd=repo_root)
    if fetch.returncode != 0:
        return False, f"git fetch origin {_MAIN_BRANCH} failed: {(fetch.stderr or fetch.stdout).strip()}", None

    verify = _run_git(["git", "rev-parse", "--verify", f"origin/{_MAIN_BRANCH}"], cwd=repo_root)
    if verify.returncode != 0:
        return (
            False,
            f"Missing ref origin/{_MAIN_BRANCH} after fetch. Ensure the remote has a {_MAIN_BRANCH} branch.",
            None,
        )

    co_main = _run_git(["git", "checkout", "-q", _MAIN_BRANCH], cwd=repo_root)
    if co_main.returncode != 0:
        return False, f"Could not checkout {_MAIN_BRANCH}: {(co_main.stderr or co_main.stdout).strip()}", None

    pull = _run_git(["git", "pull", "--ff-only", "origin", _MAIN_BRANCH], cwd=repo_root)
    if pull.returncode != 0:
        return (
            False,
            f"git pull --ff-only origin {_MAIN_BRANCH} failed (local {_MAIN_BRANCH} is not a fast-forward of the "
            f"remote). Update {_MAIN_BRANCH} (e.g. reset to origin/{_MAIN_BRANCH} after backing up) and retry.\n"
            f"{(pull.stderr or pull.stdout).strip()}",
            None,
        )

    co_task = _run_git(["git", "checkout", "-q", "-B", task_branch, _MAIN_BRANCH], cwd=repo_root)
    if co_task.returncode != 0:
        return False, f"Could not create branch {task_branch!r}: {(co_task.stderr or co_task.stdout).strip()}", None

    if has_scoped_commits:
        co_scope = _run_git(["git", "checkout", source_head, "--", f"{scope}/"], cwd=repo_root)
        if co_scope.returncode != 0:
            return (
                False,
                "Could not replay committed changes under the project scope from your previous branch "
                f"onto {_MAIN_BRANCH}. {(co_scope.stderr or co_scope.stdout).strip()}",
                None,
            )

    if stash_created:
        pop = _run_git(["git", "stash", "pop"], cwd=repo_root)
        if pop.returncode != 0:
            return (
                False,
                "git stash pop failed (merge conflicts possible). Fix conflicts or run `git stash drop` after "
                f"saving work, then retry.\n{(pop.stderr or pop.stdout).strip()}",
                None,
            )

    ok_stage2, err_stage2, staged2 = _stage_scope_and_list_cached(repo_root, scope)
    if not ok_stage2:
        return False, err_stage2, None
    if not staged2:
        return (
            False,
            "No scoped changes remained to commit after branching from main (unexpected).",
            None,
        )

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
