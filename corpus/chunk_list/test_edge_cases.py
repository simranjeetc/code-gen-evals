import pytest

from solution import chunk_list


def test_negative_size_raises():
    with pytest.raises(ValueError):
        chunk_list([1, 2], -1)


def test_size_one():
    assert chunk_list([1, 2, 3], 1) == [[1], [2], [3]]


def test_size_equals_length():
    assert chunk_list([1, 2, 3], 3) == [[1, 2, 3]]


def test_chunks_are_lists():
    chunks = chunk_list([1, 2], 1)
    assert all(isinstance(chunk, list) for chunk in chunks)


def test_input_is_not_mutated():
    original = [1, 2, 3]
    chunk_list(original, 2)
    assert original == [1, 2, 3]


def test_value_error_not_type_error():
    with pytest.raises(ValueError):
        chunk_list([1], 0)


def test_preserves_order_across_many_chunks():
    assert chunk_list(list(range(7)), 3) == [[0, 1, 2], [3, 4, 5], [6]]
