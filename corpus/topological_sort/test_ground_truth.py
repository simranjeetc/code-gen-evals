from solution import topological_sort


def _is_valid_order(nodes, edges, order):
    assert sorted(order) == sorted(nodes), (order, nodes)
    position = {node: index for index, node in enumerate(order)}
    return all(position[before] < position[after] for before, after in edges)


def test_simple_chain():
    nodes = ["a", "b", "c"]
    edges = [("a", "b"), ("b", "c")]
    order = topological_sort(nodes, edges)
    assert _is_valid_order(nodes, edges, order)


def test_nodes_without_edges_are_included():
    order = topological_sort(["a", "b", "c"], [("a", "b")])
    assert sorted(order) == ["a", "b", "c"]


def test_no_edges():
    order = topological_sort(["x", "y"], [])
    assert sorted(order) == ["x", "y"]


def test_diamond():
    nodes = ["a", "b", "c", "d"]
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
    order = topological_sort(nodes, edges)
    assert _is_valid_order(nodes, edges, order)
