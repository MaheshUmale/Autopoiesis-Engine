def main(inputs: dict) -> dict:
    """Parses JSON input data and doubles the value field."""
    data = inputs.get("data", {})
    if isinstance(data, str):
        import json
        data = json.loads(data)
    val = data.get("value", inputs.get("value", 0))
    return {"status": "success", "original_value": val, "doubled_value": val * 2}
