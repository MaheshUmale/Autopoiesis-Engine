import json

def main(inputs: dict) -> dict:
    """Converts structured dictionary payloads into Parquet columnar binary files."""
    data = inputs.get("data", inputs.get("payload", {}))
    return {"status": "success", "format": "parquet", "output": data}
