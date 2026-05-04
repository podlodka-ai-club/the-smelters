from __future__ import annotations

import json
from typing import Any

from shared.checker_utils import last_json_line_with_checker_status


def checker_passed_from_content(content: str) -> bool:
    line = last_json_line_with_checker_status(content or "")
    if not line:
        return False
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and parsed.get("status") == "passed"


def pr_created_from_state(state: dict[str, Any] | None) -> bool:
    payload = (state or {}).get("pr_create_result")
    return isinstance(payload, dict) and bool(payload.get("ok"))
