"""Fake Reviewer: no LLM, deterministic from env var FAKE_REVIEWER."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


def main() -> int:
    scenario = os.environ.get("FAKE_REVIEWER", "approve")
    task_id = int(sys.argv[1])

    if scenario == "crash":
        return 1
    if scenario == "malformed":
        print("this is not JSON")
        return 0
    if scenario == "reject":
        print(json.dumps({"approved": False, "notes": "fake rejection"}))
        return 0
    if scenario == "reject_then_approve":
        cwd_hash = hashlib.sha1(str(Path.cwd()).encode("utf-8")).hexdigest()[:12]
        state_file = Path(f"/tmp/fake_reviewer_task_{task_id}_{cwd_hash}.counter")
        seen = int(state_file.read_text()) if state_file.exists() else 0
        state_file.write_text(str(seen + 1))
        verdict = {"approved": seen >= 1, "notes": "fake" if seen >= 1 else "fix it"}
        print(json.dumps(verdict))
        return 0

    print(json.dumps({"approved": True, "notes": "fake approval"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
