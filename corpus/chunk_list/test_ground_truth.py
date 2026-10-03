import pytest

from solution import chunk_list


def test_splits_with_a_trailing_short_chunk():
    assert chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_exact_division_has_no_short_chunk():
    assert chunk_list([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_size_larger_than_input():
    assert chunk_list([1, 2], 5) == [[1, 2]]


def test_empty_input():
    assert chunk_list([], 3) == []


def test_zero_size_raises():
    with pytest.raises(ValueError):
        chunk_list([1, 2], 0)
