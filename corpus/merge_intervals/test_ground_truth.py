from solution import merge_intervals


def test_empty_input():
    assert merge_intervals([]) == []


def test_single_interval():
    assert merge_intervals([[1, 2]]) == [[1, 2]]


def test_overlapping_intervals_merge():
    assert merge_intervals([[1, 3], [2, 6]]) == [[1, 6]]


def test_unsorted_input():
    assert merge_intervals([[5, 7], [1, 3]]) == [[1, 3], [5, 7]]


def test_contained_interval_is_absorbed():
    assert merge_intervals([[1, 10], [3, 4]]) == [[1, 10]]
