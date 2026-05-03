from __future__ import annotations

import pytest

from src.smelters_yaml import (
    merge_cli_backend_overrides,
    resolve_agent_config_path,
    resolve_smelters_backends_from_yaml,
)


def test_resolve_smelters_backends_from_yaml_reads_keys() -> None:
    cfg = {
        "smelters_coder_backend": "opencode",
        "smelters_checker_backend": "gemini",
        "smelters_reviewer_backend": "claude",
    }
    b = resolve_smelters_backends_from_yaml(cfg)
    assert b.coder == "opencode"
    assert b.checker == "gemini"
    assert b.reviewer == "claude"


def test_resolve_smelters_backends_invalid_key_exits() -> None:
    with pytest.raises(SystemExit, match="invalid smelters_coder_backend"):
        resolve_smelters_backends_from_yaml({"smelters_coder_backend": "bogus"})


def test_merge_cli_backend_overrides_partial() -> None:
    y = resolve_smelters_backends_from_yaml({})
    m = merge_cli_backend_overrides(y, coder_override="gemini", checker_override=None, reviewer_override=None)
    assert m.coder == "gemini"
    assert m.checker == y.checker
    assert m.reviewer == y.reviewer


def test_resolve_agent_config_path_explicit_must_exist(tmp_path) -> None:
    p = tmp_path / "cfg.yml"
    p.write_text("x: 1\n", encoding="utf-8")
    resolved = resolve_agent_config_path(str(p))
    assert resolved == p.resolve()


def test_resolve_agent_config_path_explicit_missing_exits(tmp_path) -> None:
    with pytest.raises(SystemExit, match="not found"):
        resolve_agent_config_path(str(tmp_path / "nope.yml"))


def test_resolve_agent_config_path_default_prefers_repo_yaml(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("REPO_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "agent_config.yml"
    cfg.write_text("smelters_coder_backend: claude\n", encoding="utf-8")
    resolved = resolve_agent_config_path(None)
    assert resolved == cfg.resolve()


def test_load_config_explicit_path(tmp_path, monkeypatch) -> None:
    from shared.agent_base import load_config

    p = tmp_path / "custom.yml"
    p.write_text("smelters_coder_backend: opencode\nopencode_coder_model: custom/model\n", encoding="utf-8")
    cfg = load_config(config_path=p)
    assert cfg.get("smelters_coder_backend") == "opencode"
    assert cfg.get("opencode_coder_model") == "custom/model"
