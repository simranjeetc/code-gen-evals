import pytest

from solution import topological_sort


def test_empty_input():
    assert topological_sort([], []) == []


def test_single_node():
    assert topological_sort(["only"], []) == ["only"]


def test_cycle_is_rejected():
    with pytest.raises(ValueError):
        topological_sort(["a", "b"], [("a", "b"), ("b", "a")])


def test_self_loop_is_rejected():
    with pytest.raises(ValueError):
        topological_sort(["a"], [("a", "a")])


def test_unknown_node_is_rejected():
    with pytest.raises(ValueError):
        topological_sort(["a"], [("a", "ghost")])


def test_disconnected_components():
    nodes = ["a", "b", "c", "d"]
    edges = [("a", "b"), ("c", "d")]
    order = topological_sort(nodes, edges)
    position = {node: index for index, node in enumerate(order)}
    assert position["a"] < position["b"]
    assert position["c"] < position["d"]


def test_returns_a_list_of_all_nodes_once():
    nodes = ["a", "b", "c"]
    order = topological_sort(nodes, [("a", "b"), ("a", "c")])
    assert isinstance(order, list)
    assert sorted(order) == sorted(nodes)


def test_longer_cycle_is_rejected():
    with pytest.raises(ValueError):
        topological_sort(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")])


def test_integer_nodes():
    order = topological_sort([1, 2, 3], [(1, 3), (2, 3)])
    position = {node: index for index, node in enumerate(order)}
    assert position[1] < position[3]
    assert position[2] < position[3]
