def process_batch(items, handler):
    results = []
    failed = {}
    for index, item in enumerate(items):
        try:
            results.append(handler(item))
        except Exception as error:  # noqa: BLE001 - partial failure is the point
            failed[index] = error
    return {"ok": len(results), "failed": failed, "results": results}
