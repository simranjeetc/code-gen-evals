from solution import flatten


def test_only_empty_containers():
    assert flatten([[], ()]) == []


def test_strings_are_leaf_values():
    assert flatten(["ab", ["cd"]]) == ["ab", "cd"]


def test_dicts_are_leaf_values():
    assert flatten([{"a": 1}]) == [{"a": 1}]


def test_very_deep_nesting_does_not_raise():
    nested = 42
    for _ in range(1500):
        nested = [nested]
    assert flatten(nested) == [42]


def test_order_is_preserved():
    assert flatten([[3, 1], [2], [[4]]]) == [3, 1, 2, 4]


def test_returns_a_list():
    assert isinstance(flatten([1, 2]), list)


def test_tuple_of_tuples():
    assert flatten(((1, (2, 3)), 4)) == [1, 2, 3, 4]
