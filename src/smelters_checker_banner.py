"""Classify last checker output for Smelters failure-banner copy."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from shared.checker_utils import last_json_line_with_checker_status

_HINT_MAX = 200


class CheckerGateFailureKind(str, Enum):
    """Why the PR-create condition did not run, inferred from last checker step content."""

    EMPTY = "empty"
    NO_VALID_CONTRACT = "no_valid_contract"
    CONTRACT_FAILED = "contract_failed"
    PASSED_UNEXPECTED = "passed_unexpected"
    CHECKER_INFRA = "checker_infra"


def classify_last_checker_raw(raw: Optional[str]) -> CheckerGateFailureKind:
    if not raw or not str(raw).strip():
        return CheckerGateFailureKind.EMPTY
    line = last_json_line_with_checker_status(str(raw))
    if not line:
        return CheckerGateFailureKind.NO_VALID_CONTRACT
    try:
        parsed: Any = json.loads(line)
    except json.JSONDecodeError:
        return CheckerGateFailureKind.NO_VALID_CONTRACT
    if not isinstance(parsed, dict):
        return CheckerGateFailureKind.NO_VALID_CONTRACT
    status = parsed.get("status")
    if status == "failed":
        return CheckerGateFailureKind.CONTRACT_FAILED
    if status == "passed":
        return CheckerGateFailureKind.PASSED_UNEXPECTED
    if status == "error" and parsed.get("scope") == "checker":
        return CheckerGateFailureKind.CHECKER_INFRA
    return CheckerGateFailureKind.NO_VALID_CONTRACT


def checker_failure_hint_one_line(raw: str) -> Optional[str]:
    """Short hint when the contract is valid ``status: failed`` (tests/build)."""
    line = last_json_line_with_checker_status(raw or "")
    if not line:
        return None
    try:
        d: Any = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or d.get("status") != "failed":
        return None
    failed_tests = d.get("failed_tests")
    if isinstance(failed_tests, list) and failed_tests:
        first = failed_tests[0] if isinstance(failed_tests[0], dict) else {}
        name = str((first or {}).get("name", "")).strip() or "test"
        n = len(failed_tests)
        hint = f"{n} failing test(s); first: {name}"
        return hint if len(hint) <= _HINT_MAX else hint[: _HINT_MAX - 3] + "..."
    build_errors = d.get("build_errors")
    if isinstance(build_errors, str) and build_errors.strip():
        s = build_errors.strip().replace("\n", " ")
        return s if len(s) <= _HINT_MAX else s[: _HINT_MAX - 3] + "..."
    return "Checker reported status failed (no detail in failed_tests or build_errors)."
