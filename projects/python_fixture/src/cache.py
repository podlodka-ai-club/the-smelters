"""Tiny LRU cache. Deliberately implemented wrong."""
from __future__ import annotations

from collections import OrderedDict


class LRU:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._d: OrderedDict = OrderedDict()

    def get(self, key):
        if key not in self._d:
            return None
        return self._d[key]

    def put(self, key, value) -> None:
        if key in self._d:
            self._d[key] = value
            return
        if len(self._d) >= self.capacity:
            self._d.popitem(last=False)
        self._d[key] = value
