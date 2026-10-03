import pytest

from solution import LRUCache


def test_capacity_of_one():
    cache = LRUCache(1)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == -1
    assert cache.get("b") == 2


def test_zero_capacity_raises():
    with pytest.raises(ValueError):
        LRUCache(0)


def test_negative_capacity_raises():
    with pytest.raises(ValueError):
        LRUCache(-3)


def test_updating_a_key_does_not_grow_the_cache():
    cache = LRUCache(1)
    cache.put("a", 1)
    cache.put("a", 2)
    cache.put("a", 3)
    assert cache.get("a") == 3


def test_put_refreshes_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 10)
    cache.put("c", 3)
    assert cache.get("b") == -1
    assert cache.get("a") == 10


def test_non_string_keys():
    cache = LRUCache(2)
    cache.put((1, 2), "tuple")
    assert cache.get((1, 2)) == "tuple"


def test_repeated_misses_return_minus_one():
    cache = LRUCache(1)
    assert cache.get("x") == -1
    assert cache.get("x") == -1


def test_eviction_order_over_many_puts():
    cache = LRUCache(3)
    for key in ("a", "b", "c"):
        cache.put(key, key)
    cache.get("a")
    cache.put("d", "d")
    assert cache.get("b") == -1
    assert sorted([cache.get("a"), cache.get("c"), cache.get("d")]) == ["a", "c", "d"]
