FINAL_STATES = frozenset({"shipped", "cancelled", "refunded", "aborted"})

TRANSITIONS = {
    "new": {"submit": "pending"},
    "pending": {"pay": "paid", "cancel": "cancelled", "abort": "aborted"},
    "paid": {"ship": "shipped", "refund": "refunded", "abort": "aborted"},
}


class Order:
    def __init__(self):
        self._state = "new"
        self._history = ["new"]

    @property
    def state(self):
        return self._state

    def transition(self, event):
        if self._state in FINAL_STATES:
            raise ValueError("order is in a final state: %s" % (self._state,))
        allowed = TRANSITIONS.get(self._state, {})
        if event not in allowed:
            raise ValueError("event %r is not allowed from %r" % (event, self._state))
        self._state = allowed[event]
        self._history.append(self._state)
        return self._state

    def history(self):
        return list(self._history)
