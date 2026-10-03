import pytest

from solution import parse_duration


def test_empty_raises():
    with pytest.raises(ValueError):
        parse_duration("")


def test_unknown_unit_raises():
    with pytest.raises(ValueError):
        parse_duration("1x")


def test_repeated_unit_raises():
    with pytest.raises(ValueError):
        parse_duration("1h1h")


def test_zero_seconds():
    assert parse_duration("0s") == 0


def test_unit_without_digits_raises():
    with pytest.raises(ValueError):
        parse_duration("m30")


def test_units_in_any_order():
    assert parse_duration("30m1h") == 5400


def test_spaces_are_rejected():
    with pytest.raises(ValueError):
        parse_duration("1h 30m")


def test_returns_an_int():
    assert isinstance(parse_duration("10m"), int)
