import copy

from solution import json_diff


def apply_changes(value, changes):
    result = copy.deepcopy(value)
    for change in changes:
        path = change["path"]
        op = change["op"]
        if not path:
            result = copy.deepcopy(change["value"])
            continue
        parent = result
        for key in path[:-1]:
            parent = parent[key]
        last = path[-1]
        if op == "remove":
            del parent[last]
        else:
            parent[last] = change["value"]
    return result


def test_list_length_change_is_a_single_replace():
    assert json_diff([1, 2], [1, 2, 3]) == [
        {"path": [], "op": "replace", "value": [1, 2, 3]}
    ]


def test_type_change_is_a_replace():
    assert json_diff({"a": 1}, [1]) == [{"path": [], "op": "replace", "value": [1]}]


def test_int_to_float_is_a_replace():
    assert json_diff(1, 1.0) == [{"path": [], "op": "replace", "value": 1.0}]


def test_bool_and_int_are_distinguished():
    assert json_diff(1, True) == [{"path": [], "op": "replace", "value": True}]


def test_diff_applies_back_to_the_target():
    cases = [
        ({"a": 1, "b": 2}, {"a": 1, "c": 3}),
        ({"x": [1, 2, 3]}, {"x": [1, 9, 3]}),
        ({"x": [1, 2]}, {"x": [1, 2, 3]}),
        ([{"k": "v"}], [{"k": "w"}]),
        ({"nested": {"deep": {"value": 1}}}, {"nested": {"deep": {"value": 2}}}),
        (5, "five"),
    ]
    for original, target in cases:
        assert apply_changes(original, json_diff(original, target)) == target


def test_changes_are_sorted_by_path():
    diff = json_diff({"b": 1, "a": 1}, {"b": 2, "a": 2})
    assert [record["path"] for record in diff] == [["a"], ["b"]]


def test_empty_dicts_are_equal():
    assert json_diff({}, {}) == []


def test_returns_a_list():
    assert isinstance(json_diff(1, 2), list)
