Project: python_fixture

# Task 5: LRU cache must evict the least-recently-used key, not FIFO

## Failing test
tests/test_cache.py::test_eviction_order_is_lru

## Acceptance
- After `put("a",1); put("b",2); get("a"); put("c",3)` — keys present are "a" and "c", and "b" is evicted
- Do not hardcode keys or values in the implementation
- All existing tests in `tests/` still pass
