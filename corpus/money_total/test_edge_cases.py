import pytest

from solution import total


def test_thousands_of_pennies_do_not_drift():
    # float accumulation drifts here; exact decimal does not
    assert total(["0.01"] * 10000) == "100.00"


def test_float_drift_case_that_defeats_binary_floats():
    assert total(["0.10"] * 3) == "0.30"


def test_rounds_half_up_not_half_even():
    assert total(["2.675"]) == "2.68"
    assert total(["0.125"]) == "0.13"


def test_empty_string_raises():
    with pytest.raises(ValueError):
        total([""])


def test_bare_sign_raises():
    with pytest.raises(ValueError):
        total(["-"])


def test_two_decimal_points_raise():
    with pytest.raises(ValueError):
        total(["1.2.3"])


def test_explicit_plus_sign_is_accepted():
    assert total(["+1.50"]) == "1.50"


def test_exponent_notation_is_accepted():
    assert total(["1e2"]) == "100.00"


def test_whitespace_is_ignored():
    assert total(["  1.00  ", " 2.00"]) == "3.00"


def test_non_string_amount_raises():
    with pytest.raises(ValueError):
        total([1.0])


def test_negative_total_is_formatted_with_sign():
    assert total(["-1.00", "-2.00"]) == "-3.00"


def test_total_is_exactly_renderable_to_cents():
    result = total(["0.001"] * 1000)
    assert result == "1.00"


def test_large_values_keep_precision():
    assert total(["99999999999999.99", "0.01"]) == "100000000000000.00"


def test_mixed_magnitudes():
    assert total(["1000000.99", "-1000000.98"]) == "0.01"


def test_returns_a_string():
    assert isinstance(total(["1"]), str)
