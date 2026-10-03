from solution import json_diff


def test_equal_scalars_produce_no_changes():
    assert json_diff({"a": 1}, {"a": 1}) == []


def test_scalar_replace_at_root():
    assert json_diff(1, 2) == [{"path": [], "op": "replace", "value": 2}]


def test_dict_key_added():
    assert json_diff({"a": 1}, {"a": 1, "b": 2}) == [
        {"path": ["b"], "op": "add", "value": 2}
    ]


def test_dict_key_removed():
    assert json_diff({"a": 1, "b": 2}, {"a": 1}) == [
        {"path": ["b"], "op": "remove", "value": 2}
    ]


def test_nested_value_changed():
    assert json_diff({"a": {"b": 1}}, {"a": {"b": 2}}) == [
        {"path": ["a", "b"], "op": "replace", "value": 2}
    ]


def test_list_same_length_recurses():
    assert json_diff([1, 2], [1, 3]) == [
        {"path": [1], "op": "replace", "value": 3}
    ]
