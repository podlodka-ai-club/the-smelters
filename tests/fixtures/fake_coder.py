"""Fake Coder: no LLM, deterministic from env var FAKE_CODER. Used by tests only."""
from __future__ import annotations

import json
import os
import sys
import time


def main() -> int:
    scenario = os.environ.get("FAKE_CODER", "ok")
    task_id = int(sys.argv[1])

    if scenario == "crash":
        print("boom", file=sys.stderr)
        return 1
    if scenario == "timeout":
        time.sleep(300)
        return 0

    print(json.dumps({"ok": True, "summary": f"fake coder finished task {task_id}"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
