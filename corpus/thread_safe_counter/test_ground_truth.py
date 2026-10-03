import threading

from solution import ThreadSafeCounter


def test_starts_at_zero():
    assert ThreadSafeCounter().value() == 0


def test_increment_returns_the_new_value():
    counter = ThreadSafeCounter()
    assert counter.increment() == 1
    assert counter.increment(5) == 6


def test_default_amount_is_one():
    counter = ThreadSafeCounter()
    counter.increment()
    assert counter.value() == 1


def test_reset_returns_to_zero():
    counter = ThreadSafeCounter()
    counter.increment(7)
    counter.reset()
    assert counter.value() == 0


def test_concurrent_increments_lose_nothing():
    counter = ThreadSafeCounter()
    threads = [
        threading.Thread(target=lambda: [counter.increment() for _ in range(2000)])
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert counter.value() == 16000
