"""A tiny HTTP client wrapping the stdlib. Deliberately missing a timeout."""
from __future__ import annotations

import urllib.request


def get(url: str, *, timeout: float | None = None) -> bytes:
    with urllib.request.urlopen(url) as response:
        return response.read()
