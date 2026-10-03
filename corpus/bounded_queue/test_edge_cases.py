import pytest

from solution import BoundedQueue


def test_push_when_full_drops_the_oldest():
    queue = BoundedQueue(2)
    queue.push("a")
    queue.push("b")
    queue.push("c")
    assert list(queue) == ["b", "c"]


def test_push_when_full_never_raises():
    queue = BoundedQueue(1)
    queue.push(1)
    queue.push(2)
    queue.push(3)
    assert list(queue) == [3]


def test_never_exceeds_capacity_under_many_pushes():
    queue = BoundedQueue(3)
    for value in range(100):
        queue.push(value)
        assert len(queue) <= 3


def test_len_is_exactly_capacity_after_overflow():
    queue = BoundedQueue(4)
    for value in range(10):
        queue.push(value)
    assert len(queue) == 4


def test_peek_after_overflow_returns_the_new_oldest():
    queue = BoundedQueue(2)
    queue.push("a")
    queue.push("b")
    queue.push("c")
    assert queue.peek() == "b"


def test_empty_after_draining():
    queue = BoundedQueue(2)
    queue.push(1)
    queue.pop()
    assert queue.pop() is None
    assert len(queue) == 0


def test_negative_capacity_raises():
    with pytest.raises(ValueError):
        BoundedQueue(-1)


def test_non_integer_capacity_raises():
    with pytest.raises(ValueError):
        BoundedQueue("3")


def test_pop_returns_items_in_order_after_overflow():
    queue = BoundedQueue(3)
    for value in (1, 2, 3, 4, 5):
        queue.push(value)
    assert [queue.pop(), queue.pop(), queue.pop()] == [3, 4, 5]


def test_capacity_of_one_repeatedly_overwritten():
    queue = BoundedQueue(1)
    for value in "abc":
        queue.push(value)
    assert queue.pop() == "c"
    assert queue.pop() is None


def test_iteration_does_not_consume():
    queue = BoundedQueue(3)
    queue.push(1)
    queue.push(2)
    assert list(queue) == [1, 2]
    assert list(queue) == [1, 2]


def test_pop_on_empty_does_not_raise():
    queue = BoundedQueue(2)
    assert queue.pop() is None


def test_none_can_be_stored_and_is_distinguishable_by_len():
    queue = BoundedQueue(2)
    queue.push(None)
    assert len(queue) == 1
    assert queue.pop() is None
    assert len(queue) == 0
