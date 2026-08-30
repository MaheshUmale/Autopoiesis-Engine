import json

def _double_numbers(obj):
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return obj * 2
    elif isinstance(obj, dict):
        return {k: _double_numbers(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_double_numbers(item) for item in obj]
    return obj

def main(inputs: dict) -> dict:
    """Parses JSON payload data and doubles numerical value fields."""
    payload = inputs.get("payload", inputs.get("data", inputs))
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            pass
    transformed = _double_numbers(payload)
    return {"status": "success", "data": transformed, "output": transformed}
