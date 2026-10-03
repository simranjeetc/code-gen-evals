import pytest

from solution import BoundedQueue


def test_starts_empty():
    queue = BoundedQueue(3)
    assert len(queue) == 0
    assert queue.pop() is None


def test_push_and_pop_is_fifo():
    queue = BoundedQueue(3)
    queue.push("a")
    queue.push("b")
    assert queue.pop() == "a"
    assert queue.pop() == "b"


def test_peek_does_not_remove():
    queue = BoundedQueue(3)
    queue.push("a")
    assert queue.peek() == "a"
    assert len(queue) == 1


def test_zero_capacity_raises():
    with pytest.raises(ValueError):
        BoundedQueue(0)


def test_iteration_is_oldest_first():
    queue = BoundedQueue(3)
    queue.push(1)
    queue.push(2)
    assert list(queue) == [1, 2]


def test_len_tracks_size():
    queue = BoundedQueue(2)
    queue.push(1)
    queue.push(2)
    assert len(queue) == 2
