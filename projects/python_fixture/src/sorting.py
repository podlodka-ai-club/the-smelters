"""Sort a list of dicts by `priority`, but keep `inserted_at` order among equals."""
from __future__ import annotations


def by_priority(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda item: (item["priority"], -item["inserted_at"]))
