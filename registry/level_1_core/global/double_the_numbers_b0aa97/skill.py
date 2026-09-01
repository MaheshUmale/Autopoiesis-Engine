def _double_values(obj):
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return obj * 2
    elif isinstance(obj, dict):
        return {k: _double_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_double_values(item) for item in obj]
    return obj

def main(inputs: dict) -> dict:
    """Autonomously synthesized micro-skill for: double the numbers"""
    raw_data = inputs.get("data", inputs.get("payload", inputs))
    doubled = _double_values(raw_data)
    return {"status": "success", "data": doubled, "output": doubled}
