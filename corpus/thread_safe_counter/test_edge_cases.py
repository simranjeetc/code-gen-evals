import sys
import threading

from solution import ThreadSafeCounter


def _run_concurrently(target, thread_count):
    """Run threads under an aggressive switch interval to force interleaving."""
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=target) for _ in range(thread_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(previous)


def test_negative_amount():
    counter = ThreadSafeCounter()
    counter.increment(-2)
    assert counter.value() == -2


def test_zero_amount():
    counter = ThreadSafeCounter()
    counter.increment(0)
    assert counter.value() == 0


def test_value_is_an_int():
    counter = ThreadSafeCounter()
    counter.increment(3)
    assert isinstance(counter.value(), int)


def test_concurrent_increments_with_varying_amounts():
    counter = ThreadSafeCounter()

    def worker():
        for _ in range(500):
            counter.increment(2)

    _run_concurrently(worker, 6)
    assert counter.value() == 6000


def test_concurrent_mixed_increment_and_reset_does_not_error():
    counter = ThreadSafeCounter()

    def worker():
        for _ in range(300):
            counter.increment()
            counter.value()

    _run_concurrently(worker, 4)
    assert counter.value() == 1200


def test_many_short_lived_threads():
    counter = ThreadSafeCounter()
    for _ in range(12):
        _run_concurrently(lambda: [counter.increment() for _ in range(100)], 4)
    assert counter.value() == 12 * 4 * 100


def test_reset_between_runs():
    counter = ThreadSafeCounter()
    _run_concurrently(lambda: [counter.increment() for _ in range(100)], 4)
    counter.reset()
    assert counter.value() == 0
