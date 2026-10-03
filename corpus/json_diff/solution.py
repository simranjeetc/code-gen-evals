def _walk(a, b, path, changes):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in a:
            if key not in b:
                changes.append({"path": path + [key], "op": "remove", "value": a[key]})
        for key in b:
            if key not in a:
                changes.append({"path": path + [key], "op": "add", "value": b[key]})
            else:
                _walk(a[key], b[key], path + [key], changes)
        return

    if isinstance(a, list) and isinstance(b, list):
        if len(a) == len(b):
            for index in range(len(a)):
                _walk(a[index], b[index], path + [index], changes)
        else:
            changes.append({"path": path, "op": "replace", "value": b})
        return

    if a != b or type(a) is not type(b):
        changes.append({"path": path, "op": "replace", "value": b})


def json_diff(a, b):
    changes = []
    _walk(a, b, [], changes)
    changes.sort(key=lambda change: ([str(part) for part in change["path"]], change["op"]))
    return changes
