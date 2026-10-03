from solution import merge_intervals


def test_touching_intervals_merge():
    assert merge_intervals([[1, 3], [3, 5]]) == [[1, 5]]


def test_duplicate_intervals_collapse():
    assert merge_intervals([[2, 4], [2, 4]]) == [[2, 4]]


def test_zero_length_interval():
    assert merge_intervals([[5, 5]]) == [[5, 5]]


def test_zero_length_between_two_others():
    assert merge_intervals([[1, 3], [5, 5], [2, 4]]) == [[1, 4], [5, 5]]


def test_returns_lists_not_tuples():
    result = merge_intervals([(1, 2), (3, 4)])
    assert all(isinstance(item, list) for item in result)


def test_input_is_not_mutated():
    original = [[3, 4], [1, 2]]
    merge_intervals(original)
    assert original == [[3, 4], [1, 2]]


def test_many_intervals_merge_into_one():
    assert merge_intervals([[1, 2], [2, 3], [3, 4], [4, 5]]) == [[1, 5]]


def test_gap_prevents_merging():
    assert merge_intervals([[1, 2], [3, 4]]) == [[1, 2], [3, 4]]
