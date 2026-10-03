import pytest

from solution import retry_with_backoff


def test_delay_sequence_doubles():
    sleeps = []

    @retry_with_backoff((ValueError,), attempts=4, sleep=sleeps.append)
    def work():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        work()
    assert sleeps == [0.1, 0.2, 0.4]


def test_delays_are_capped_at_max_delay():
    sleeps = []

    @retry_with_backoff((ValueError,), attempts=5, base_delay=1.0, max_delay=2.5, sleep=sleeps.append)
    def work():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        work()
    assert sleeps == [1.0, 2.0, 2.5, 2.5]


def test_single_attempt_never_sleeps():
    sleeps = []

    @retry_with_backoff((ValueError,), attempts=1, sleep=sleeps.append)
    def work():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        work()
    assert sleeps == []


def test_multiple_exception_types_are_caught():
    state = {"calls": 0}

    @retry_with_backoff((ValueError, KeyError), attempts=3, sleep=lambda _: None)
    def work():
        state["calls"] += 1
        if state["calls"] == 1:
            raise ValueError("first")
        if state["calls"] == 2:
            raise KeyError("second")
        return "third"

    assert work() == "third"
    assert state["calls"] == 3


def test_reraised_error_is_the_last_one():
    @retry_with_backoff((ValueError,), attempts=2, sleep=lambda _: None)
    def work():
        raise ValueError("final message")

    with pytest.raises(ValueError, match="final message"):
        work()


def test_max_delay_can_be_below_base_delay():
    sleeps = []

    @retry_with_backoff((ValueError,), attempts=3, base_delay=5.0, max_delay=1.0, sleep=sleeps.append)
    def work():
        raise ValueError("boom")

    with pytest.raises(ValueError):
        work()
    assert sleeps == [1.0, 1.0]
