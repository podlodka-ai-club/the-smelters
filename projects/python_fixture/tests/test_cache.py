from cache import LRU


def test_eviction_order_is_lru() -> None:
    cache = LRU(2)
    cache.put("a", 1)
    cache.put("b", 2)
    _ = cache.get("a")
    cache.put("c", 3)
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_capacity_respected() -> None:
    cache = LRU(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    present = [key for key in ("a", "b", "c") if cache.get(key) is not None]
    assert len(present) == 2
