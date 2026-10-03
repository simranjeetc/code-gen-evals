import pytest

from solution import process_batch


def test_every_item_attempted_exactly_once():
    seen = []

    def handler(value):
        seen.append(value)
        return value

    process_batch([1, 2, 3], handler)
    assert seen == [1, 2, 3]


def test_successful_item_is_never_retried():
    calls = []

    def handler(value):
        calls.append(value)
        if value == 1:
            raise ValueError("once")
        return value

    process_batch([1, 2], handler)
    assert calls.count(1) == 1


def test_all_items_fail():
    def handler(value):
        raise KeyError(value)

    report = process_batch([1, 2, 3], handler)
    assert report["ok"] == 0
    assert report["results"] == []
    assert sorted(report["failed"]) == [0, 1, 2]


def test_duplicate_values_are_distinct_indices():
    def handler(value):
        if value == "x":
            raise ValueError("no")
        return value

    report = process_batch(["x", "y", "x"], handler)
    assert sorted(report["failed"]) == [0, 2]
    assert report["results"] == ["y"]


def test_failure_map_holds_the_exception_instance():
    error = ValueError("specific")

    def handler(value):
        raise error

    report = process_batch([1], handler)
    assert report["failed"][0] is error


def test_handler_returning_none_still_counts_as_success():
    report = process_batch([1, 2], lambda x: None)
    assert report["ok"] == 2
    assert report["results"] == [None, None]


def test_non_exception_handler_outputs_are_preserved():
    report = process_batch(["a", "b"], lambda x: {"v": x})
    assert report["results"] == [{"v": "a"}, {"v": "b"}]


def test_report_has_exactly_the_three_keys():
    assert set(process_batch([1], lambda x: x)) == {"ok", "failed", "results"}


def test_base_exception_subclass_that_is_not_exception_is_not_swallowed():
    # KeyboardInterrupt must propagate; only Exception subclasses are failures.
    def handler(value):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        process_batch([1], handler)


def test_large_batch_counts_are_exact():
    def handler(value):
        if value % 7 == 0:
            raise ValueError("seven")
        return value

    report = process_batch(list(range(1000)), handler)
    assert report["ok"] == 1000 - len([v for v in range(1000) if v % 7 == 0])
    assert report["ok"] + len(report["failed"]) == 1000


def test_ok_matches_len_of_results():
    def handler(value):
        if value in (2, 5):
            raise ValueError("skip")
        return value

    report = process_batch(range(10), handler)
    assert report["ok"] == len(report["results"])


def test_empty_batch_does_not_call_handler():
    called = []
    process_batch([], lambda x: called.append(x))
    assert called == []
