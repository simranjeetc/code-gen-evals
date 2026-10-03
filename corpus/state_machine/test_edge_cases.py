import pytest

from solution import Order


def test_final_state_rejects_every_event():
    order = Order()
    order.transition("submit")
    order.transition("cancel")
    for event in ("submit", "pay", "ship", "cancel", "abort", "refund"):
        with pytest.raises(ValueError):
            order.transition(event)


def test_rejected_event_leaves_state_unchanged():
    order = Order()
    with pytest.raises(ValueError):
        order.transition("ship")
    assert order.state == "new"


def test_rejected_event_does_not_touch_history():
    order = Order()
    with pytest.raises(ValueError):
        order.transition("ship")
    assert order.history() == ["new"]


def test_abort_from_pending():
    order = Order()
    order.transition("submit")
    assert order.transition("abort") == "aborted"


def test_abort_from_paid():
    order = Order()
    order.transition("submit")
    order.transition("pay")
    assert order.transition("abort") == "aborted"


def test_abort_from_new_is_rejected():
    with pytest.raises(ValueError):
        Order().transition("abort")


def test_cannot_ship_from_pending():
    order = Order()
    order.transition("submit")
    with pytest.raises(ValueError):
        order.transition("ship")


def test_refund_after_ship_is_rejected():
    order = Order()
    for event in ("submit", "pay", "ship"):
        order.transition(event)
    with pytest.raises(ValueError):
        order.transition("refund")


def test_cancel_after_pay_is_rejected():
    order = Order()
    order.transition("submit")
    order.transition("pay")
    with pytest.raises(ValueError):
        order.transition("cancel")


def test_double_submit_is_rejected():
    order = Order()
    order.transition("submit")
    with pytest.raises(ValueError):
        order.transition("submit")


def test_history_is_a_copy_not_internal_state():
    order = Order()
    order.transition("submit")
    snapshot = order.history()
    snapshot.append("tampered")
    assert order.history() == ["new", "pending"]


def test_refund_path_from_paid():
    order = Order()
    order.transition("submit")
    order.transition("pay")
    assert order.transition("refund") == "refunded"


def test_two_independent_orders_do_not_share_state():
    first = Order()
    second = Order()
    first.transition("submit")
    assert second.state == "new"


def test_unknown_event_is_rejected():
    with pytest.raises(ValueError):
        Order().transition("teleport")


def test_state_is_a_string():
    assert isinstance(Order().state, str)
