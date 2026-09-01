def main(inputs: dict) -> dict:
    """Query JSON documents with dot-path expressions (e.g., 'users.0.name')."""
    import json
    data = inputs.get("data", {})
    query = inputs.get("query", "")

    if isinstance(data, str):
        data = json.loads(data)

    if not query:
        return {"status": "error", "error": "query is required"}

    parts = query.split(".")
    current = data
    try:
        for part in parts:
            if part.isdigit():
                current = current[int(part)]
            else:
                current = current[part]
        return {"status": "success", "result": current}
    except (KeyError, IndexError, TypeError) as e:
        return {"status": "error", "error": f"Query '{query}' failed: {e}"}
