def flatten(items):
    result = []
    stack = [iter(items)]
    while stack:
        try:
            item = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        if isinstance(item, (list, tuple)):
            stack.append(iter(item))
        else:
            result.append(item)
    return result
