def merge_intervals(intervals):
    if not intervals:
        return []
    ordered = sorted(([pair[0], pair[1]] for pair in intervals), key=lambda p: (p[0], p[1]))
    merged = [ordered[0][:]]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start <= last[1]:
            if end > last[1]:
                last[1] = end
        else:
            merged.append([start, end])
    return merged
