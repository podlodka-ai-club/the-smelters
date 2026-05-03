"""Smelters orchestrator: backends + models from YAML, CLI overrides optional."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, FrozenSet, NamedTuple, Optional


SMELTERS_CODER_BACKENDS: FrozenSet[str] = frozenset(
    {"claude", "gemini", "claude-cli", "opencode"}
)
SMELTERS_CHECKER_BACKENDS: FrozenSet[str] = frozenset(
    {"gemini", "claude-cli", "opencode"}
)
SMELTERS_REVIEWER_BACKENDS: FrozenSet[str] = frozenset({"claude", "opencode"})


DEFAULT_SMELTERS_CODER_BACKEND = "claude"
DEFAULT_SMELTERS_CHECKER_BACKEND = "gemini"
DEFAULT_SMELTERS_REVIEWER_BACKEND = "claude"


class SmeltersResolvedBackends(NamedTuple):
    coder: str
    checker: str
    reviewer: str


def _parse_backend(raw: Any, *, allowed: FrozenSet[str], field: str, fallback: str) -> str:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return fallback
    s = str(raw).strip().lower()
    if s not in allowed:
        sys.exit(
            f"ERROR: invalid {field} in agent config: {raw!r}. Allowed: {sorted(allowed)}"
        )
    return s


def resolve_smelters_backends_from_yaml(cfg: dict[str, Any]) -> SmeltersResolvedBackends:
    """Read ``smelters_*_backend`` keys; missing keys use conservative defaults."""
    return SmeltersResolvedBackends(
        coder=_parse_backend(
            cfg.get("smelters_coder_backend"),
            allowed=SMELTERS_CODER_BACKENDS,
            field="smelters_coder_backend",
            fallback=DEFAULT_SMELTERS_CODER_BACKEND,
        ),
        checker=_parse_backend(
            cfg.get("smelters_checker_backend"),
            allowed=SMELTERS_CHECKER_BACKENDS,
            field="smelters_checker_backend",
            fallback=DEFAULT_SMELTERS_CHECKER_BACKEND,
        ),
        reviewer=_parse_backend(
            cfg.get("smelters_reviewer_backend"),
            allowed=SMELTERS_REVIEWER_BACKENDS,
            field="smelters_reviewer_backend",
            fallback=DEFAULT_SMELTERS_REVIEWER_BACKEND,
        ),
    )


def merge_cli_backend_overrides(
    yaml_backends: SmeltersResolvedBackends,
    *,
    coder_override: Optional[str],
    checker_override: Optional[str],
    reviewer_override: Optional[str],
) -> SmeltersResolvedBackends:
    """CLI flags override YAML when provided."""
    return SmeltersResolvedBackends(
        coder=coder_override if coder_override is not None else yaml_backends.coder,
        checker=checker_override if checker_override is not None else yaml_backends.checker,
        reviewer=reviewer_override if reviewer_override is not None else yaml_backends.reviewer,
    )


def resolve_agent_config_path(cli_path: str | None, *, cwd: Path | None = None) -> Path:
    """Resolve YAML path for ``load_config(config_path=…)``.

    If ``cli_path`` is set, it must exist. Otherwise return first existing default location,
    or ``cwd/agent_config.yml`` as the canonical default path (may not exist yet).
    """
    base = cwd or Path.cwd()
    if cli_path:
        p = Path(cli_path).expanduser().resolve()
        if not p.is_file():
            sys.exit(f"ERROR: --agent-config file not found: {p}")
        return p
    for candidate in (
        Path(os.environ.get("REPO_ROOT", str(base))) / "agent_config.yml",
        base / "agent_config.yml",
    ):
        if candidate.is_file():
            return candidate.resolve()
    return (base / "agent_config.yml").resolve()
