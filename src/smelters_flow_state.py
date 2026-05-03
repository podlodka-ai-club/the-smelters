from __future__ import annotations

import json
from typing import Any


def checker_passed_from_content(content: str) -> bool:
    lines = [line.strip() for line in (content or "").splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed.get("status") == "passed"
    return False


def pr_created_from_state(state: dict[str, Any] | None) -> bool:
    payload = (state or {}).get("pr_create_result")
    return isinstance(payload, dict) and bool(payload.get("ok"))
