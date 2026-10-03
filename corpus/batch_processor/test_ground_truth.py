from solution import process_batch


def test_all_succeed():
    report = process_batch([1, 2, 3], lambda x: x * 2)
    assert report["ok"] == 3
    assert report["results"] == [2, 4, 6]
    assert report["failed"] == {}


def test_empty_batch():
    assert process_batch([], lambda x: x) == {"ok": 0, "failed": {}, "results": []}


def test_one_failure_is_recorded():
    def handler(value):
        if value == 2:
            raise ValueError("bad")
        return value

    report = process_batch([1, 2, 3], handler)
    assert report["ok"] == 2
    assert list(report["failed"]) == [1]
    assert isinstance(report["failed"][1], ValueError)


def test_failure_does_not_stop_later_items():
    def handler(value):
        if value == 1:
            raise RuntimeError("boom")
        return value * 10

    report = process_batch([1, 2, 3], handler)
    assert report["results"] == [20, 30]


def test_results_keep_original_order_of_successes():
    def handler(value):
        if value % 2:
            raise ValueError("odd")
        return value

    report = process_batch([1, 2, 3, 4], handler)
    assert report["results"] == [2, 4]
