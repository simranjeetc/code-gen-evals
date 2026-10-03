from solution import flatten


def test_already_flat():
    assert flatten([1, 2, 3]) == [1, 2, 3]


def test_one_level():
    assert flatten([1, [2, 3]]) == [1, 2, 3]


def test_tuples_are_flattened():
    assert flatten([(1, 2), (3,)]) == [1, 2, 3]


def test_mixed_nesting():
    assert flatten([1, [2, [3, [4]]]]) == [1, 2, 3, 4]


def test_empty_input():
    assert flatten([]) == []
