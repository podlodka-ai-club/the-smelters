"""Shared JSON validation helpers for code_checker agents."""
from __future__ import annotations

import json
from typing import Any

from shared.constants import MAX_BUILD_ERRORS_LEN, MAX_FAILED_TESTS, MAX_MESSAGE_LEN

_MALFORMED: dict[str, Any] = {
    "status": "failed",
    "failed_tests": [],
    "build_errors": "malformed checker output",
    "timeout": False,
    "flaky": False,
}

_NO_CONTRACT_BUILD_ERRORS = (
    "checker did not emit a final JSON object line with "
    '"status": "passed" or "failed" '
    "(subprocess exit code 0 is not the Smelters gate)"
)


def emit_checker_infrastructure_json(message: str, detail: str = "") -> str:
    """Single-line JSON for checker/tooling failures (not test/build failures)."""
    payload: dict[str, Any] = {
        "status": "error",
        "scope": "checker",
        "message": clamp_str(message, MAX_MESSAGE_LEN),
        "detail": clamp_str(detail, MAX_BUILD_ERRORS_LEN) if detail else "",
    }
    return json.dumps(payload)


def clamp_str(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    head = limit // 2
    tail = limit - head
    return text[:head] + text[-tail:]


def clamp_failed_tests(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for raw in items[:MAX_FAILED_TESTS]:
        if not isinstance(raw, dict):
            continue
        out.append(
            {
                "name": clamp_str(raw.get("name", ""), MAX_MESSAGE_LEN),
                "message": clamp_str(raw.get("message", ""), MAX_MESSAGE_LEN),
                "location": clamp_str(raw.get("location", ""), MAX_MESSAGE_LEN),
            }
        )
    return out


def last_json_line_with_checker_status(text: str) -> str | None:
    """Return the last non-empty line that parses as a JSON object containing a ``status`` key."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    for line in reversed(lines):
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            parsed = json.loads(line)
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, dict) and "status" in parsed:
            return line
    return None


def normalize_checker_stdout_to_json_content(text: str) -> str:
    """Normalize noisy checker stdout to a single JSON line matching the Smelters checker contract."""
    line = last_json_line_with_checker_status(text or "")
    if line:
        try:
            parsed = json.loads(line)
        except (ValueError, TypeError, json.JSONDecodeError):
            parsed = None
        if (
            isinstance(parsed, dict)
            and parsed.get("status") == "error"
            and parsed.get("scope") == "checker"
        ):
            return emit_checker_infrastructure_json(
                str(parsed.get("message") or "checker tooling error"),
                str(parsed.get("detail") or ""),
            )
        normalized = extract_and_validate_json(line)
        return json.dumps(normalized)
    return emit_checker_infrastructure_json(
        "Checker did not emit valid contract JSON after exit 0",
        _NO_CONTRACT_BUILD_ERRORS,
    )


def extract_and_validate_json(text: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return dict(_MALFORMED)
    candidate = lines[-1].strip()
    try:
        parsed = json.loads(candidate)
    except (ValueError, TypeError):
        return dict(_MALFORMED)
    if not isinstance(parsed, dict):
        return dict(_MALFORMED)

    status_raw = parsed.get("status")
    if status_raw not in ("passed", "failed"):
        return dict(_MALFORMED)

    return {
        "status": status_raw,
        "failed_tests": clamp_failed_tests(parsed.get("failed_tests", [])),
        "build_errors": clamp_str(parsed.get("build_errors", ""), MAX_BUILD_ERRORS_LEN),
        "timeout": bool(parsed.get("timeout", False)),
        "flaky": bool(parsed.get("flaky", False)),
    }
