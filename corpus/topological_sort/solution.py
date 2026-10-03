def topological_sort(nodes, edges):
    ordered_nodes = list(nodes)
    indegree = {node: 0 for node in ordered_nodes}
    adjacency = {node: [] for node in ordered_nodes}

    for before, after in edges:
        if before not in indegree or after not in indegree:
            raise ValueError("edge references a node that is not in nodes")
        adjacency[before].append(after)
        indegree[after] += 1

    queue = [node for node in ordered_nodes if indegree[node] == 0]
    result = []
    head = 0
    while head < len(queue):
        node = queue[head]
        head += 1
        result.append(node)
        for neighbour in adjacency[node]:
            indegree[neighbour] -= 1
            if indegree[neighbour] == 0:
                queue.append(neighbour)

    if len(result) != len(ordered_nodes):
        raise ValueError("graph contains a cycle")
    return result
