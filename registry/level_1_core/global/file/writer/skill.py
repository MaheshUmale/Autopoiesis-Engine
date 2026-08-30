import json, os

def main(inputs: dict) -> dict:
    """Writes content or JSON data to a destination file path."""
    filepath = inputs.get("filepath", inputs.get("file_path", inputs.get("saved_to", "result.json")))
    if isinstance(filepath, dict):
        filepath = filepath.get("file_path", filepath.get("filepath", "result.json"))
    data = inputs.get("data", inputs.get("output", inputs.get("payload", inputs)))
    os.makedirs(os.path.dirname(os.path.abspath(str(filepath))) or '.', exist_ok=True)
    with open(str(filepath), "w", encoding="utf-8") as f:
        if isinstance(data, (dict, list)):
            json.dump(data, f, indent=2)
        else:
            f.write(str(data))
    return {"status": "success", "saved_to": str(filepath), "data": data}
