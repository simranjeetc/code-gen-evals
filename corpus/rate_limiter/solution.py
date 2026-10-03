import time


class RateLimiter:
    def __init__(self, rate, per_seconds, clock=None):
        if rate <= 0 or per_seconds <= 0:
            raise ValueError("rate and per_seconds must be positive")
        self.rate = float(rate)
        self.per_seconds = float(per_seconds)
        self._clock = clock if clock is not None else time.monotonic
        self._tokens = float(rate)
        self._last = self._clock()

    def _refill(self):
        now = self._clock()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(
                self.rate, self._tokens + elapsed * (self.rate / self.per_seconds)
            )
            self._last = now

    def allow(self, n=1):
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise ValueError("n must be a positive integer")
        self._refill()
        if n > self.rate:
            return False
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False
