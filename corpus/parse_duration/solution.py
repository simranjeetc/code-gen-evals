import re

_UNITS = {"h": 3600, "m": 60, "s": 1}
_GROUPS = re.compile(r"(\d+)([hms])")


def parse_duration(text):
    if not isinstance(text, str) or not text:
        raise ValueError("duration must be a non-empty string")
    if "".join(value + unit for value, unit in _GROUPS.findall(text)) != text:
        raise ValueError("malformed duration: %r" % (text,))

    total = 0
    seen = set()
    for value, unit in _GROUPS.findall(text):
        if unit in seen:
            raise ValueError("repeated unit: %r" % (unit,))
        seen.add(unit)
        total += int(value) * _UNITS[unit]
    return total
