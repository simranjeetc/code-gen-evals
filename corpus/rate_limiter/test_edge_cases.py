import pytest

from solution import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_partial_refill_grants_one_token():
    clock = FakeClock()
    limiter = RateLimiter(rate=10, per_seconds=1, clock=clock)
    assert limiter.allow(10) is True
    clock.advance(0.5)
    assert limiter.allow(5) is True
    assert limiter.allow(1) is False


def test_refill_is_capped_at_rate():
    clock = FakeClock()
    limiter = RateLimiter(rate=5, per_seconds=1, clock=clock)
    assert limiter.allow(5) is True
    clock.advance(100.0)
    assert all(limiter.allow() for _ in range(5))
    assert limiter.allow() is False


def test_negative_n_raises():
    limiter = RateLimiter(rate=3, per_seconds=1, clock=FakeClock())
    with pytest.raises(ValueError):
        limiter.allow(-1)


def test_allow_exactly_rate():
    clock = FakeClock()
    limiter = RateLimiter(rate=4, per_seconds=2, clock=clock)
    assert limiter.allow(4) is True
    assert limiter.allow(1) is False


def test_rejected_request_consumes_nothing():
    clock = FakeClock()
    limiter = RateLimiter(rate=3, per_seconds=1, clock=clock)
    assert limiter.allow(3) is True
    assert limiter.allow(1) is False
    clock.advance(1 / 3.0 + 1e-9)
    assert limiter.allow(1) is True


def test_invalid_rate_raises():
    with pytest.raises(ValueError):
        RateLimiter(rate=0, per_seconds=1, clock=FakeClock())


def test_invalid_per_seconds_raises():
    with pytest.raises(ValueError):
        RateLimiter(rate=1, per_seconds=0, clock=FakeClock())


def test_default_clock_is_used_when_omitted():
    limiter = RateLimiter(rate=1, per_seconds=1)
    assert limiter.allow() is True
