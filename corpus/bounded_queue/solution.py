from collections import deque


class BoundedQueue:
    def __init__(self, capacity):
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._items = deque()

    def push(self, item):
        if len(self._items) >= self.capacity:
            self._items.popleft()
        self._items.append(item)

    def pop(self):
        if not self._items:
            return None
        return self._items.popleft()

    def peek(self):
        if not self._items:
            return None
        return self._items[0]

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(list(self._items))
