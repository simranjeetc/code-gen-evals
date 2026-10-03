import pytest

from solution import retry_with_backoff


def test_success_on_first_attempt():
    state = {"calls": 0}
    sleeps = []

    @retry_with_backoff((ValueError,), attempts=3, sleep=sleeps.append)
    def work():
        state["calls"] += 1
        return "ok"

    assert work() == "ok"
    assert state["calls"] == 1
    assert sleeps == []


def test_retries_then_succeeds():
    state = {"calls": 0}
    sleeps = []

    @retry_with_backoff((ValueError,), attempts=3, sleep=sleeps.append)
    def work():
        state["calls"] += 1
        if state["calls"] < 3:
            raise ValueError("boom")
        return state["calls"]

    assert work() == 3
    assert sleeps == [0.1, 0.2]


def test_exhausted_attempts_reraise():
    state = {"calls": 0}

    @retry_with_backoff((ValueError,), attempts=2, sleep=lambda _: None)
    def work():
        state["calls"] += 1
        raise ValueError("always")

    with pytest.raises(ValueError):
        work()
    assert state["calls"] == 2


def test_unlisted_exception_is_not_retried():
    state = {"calls": 0}

    @retry_with_backoff((ValueError,), attempts=5, sleep=lambda _: None)
    def work():
        state["calls"] += 1
        raise KeyError("nope")

    with pytest.raises(KeyError):
        work()
    assert state["calls"] == 1


def test_arguments_are_forwarded():
    @retry_with_backoff((ValueError,), attempts=2, sleep=lambda _: None)
    def add(a, b=0):
        return a + b

    assert add(2, b=3) == 5
