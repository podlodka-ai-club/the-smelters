"""Shared constants for both agents/ and agno_agents/ implementations."""
from __future__ import annotations

import re

CHECK_TIMEOUT_SECS = 300
MAX_TURNS = 14
MAX_MESSAGE_LEN = 400
MAX_BUILD_ERRORS_LEN = 4000
MAX_FAILED_TESTS = 30

BASH_DENY = [
    re.compile(r"\brm\s+-rf\s+/"),
    re.compile(r"\bgit\s+(push|commit|reset|merge|rebase)\b"),
    re.compile(r"\bcurl\b"),
    re.compile(r"\bwget\b"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\buv\s+pip\s+install\b"),
    re.compile(r"\bsudo\b"),
]
