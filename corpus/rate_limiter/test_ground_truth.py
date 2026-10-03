import pytest

from solution import RateLimiter


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_bucket_starts_full():
    clock = FakeClock()
    limiter = RateLimiter(rate=5, per_seconds=1, clock=clock)
    assert all(limiter.allow() for _ in range(5))


def test_exhausted_bucket_rejects():
    clock = FakeClock()
    limiter = RateLimiter(rate=2, per_seconds=1, clock=clock)
    limiter.allow()
    limiter.allow()
    assert limiter.allow() is False


def test_refills_after_time_passes():
    clock = FakeClock()
    limiter = RateLimiter(rate=2, per_seconds=1, clock=clock)
    limiter.allow()
    limiter.allow()
    clock.advance(1.0)
    assert limiter.allow() is True


def test_request_larger_than_rate_is_rejected():
    limiter = RateLimiter(rate=3, per_seconds=1, clock=FakeClock())
    assert limiter.allow(4) is False


def test_zero_n_raises():
    limiter = RateLimiter(rate=3, per_seconds=1, clock=FakeClock())
    with pytest.raises(ValueError):
        limiter.allow(0)
