import pytest

from solution import Order


def test_starts_in_new():
    assert Order().state == "new"


def test_submit_moves_to_pending():
    order = Order()
    assert order.transition("submit") == "pending"


def test_full_happy_path():
    order = Order()
    order.transition("submit")
    order.transition("pay")
    assert order.transition("ship") == "shipped"


def test_invalid_event_raises():
    with pytest.raises(ValueError):
        Order().transition("pay")


def test_history_starts_with_new():
    assert Order().history() == ["new"]


def test_history_records_each_state():
    order = Order()
    order.transition("submit")
    order.transition("pay")
    assert order.history() == ["new", "pending", "paid"]
