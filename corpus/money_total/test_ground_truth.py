import pytest

from solution import total


def test_simple_sum():
    assert total(["1.10", "2.20"]) == "3.30"


def test_empty_list():
    assert total([]) == "0.00"


def test_negative_amounts():
    assert total(["5.00", "-2.50"]) == "2.50"


def test_rounds_to_two_places():
    assert total(["1.005"]) == "1.01"


def test_whole_numbers_get_two_places():
    assert total(["7"]) == "7.00"


def test_invalid_string_raises():
    with pytest.raises(ValueError):
        total(["abc"])
