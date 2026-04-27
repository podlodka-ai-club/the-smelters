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
