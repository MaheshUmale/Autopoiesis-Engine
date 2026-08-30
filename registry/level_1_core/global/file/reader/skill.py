import json, os

def main(inputs: dict) -> dict:
    """Reads file contents from disk returning formatted text or JSON objects."""
    filepath = inputs.get("filepath", inputs.get("file_path", inputs.get("payload", "")))
    if isinstance(filepath, dict):
        filepath = filepath.get("file_path", filepath.get("filepath", ""))
    if not filepath or not os.path.exists(str(filepath)):
        return {"status": "error", "error": f"File not found: {filepath}"}
    with open(str(filepath), "r", encoding="utf-8") as f:
        content = f.read()
    try:
        parsed = json.loads(content)
        return {"status": "success", "data": parsed, "output": parsed, "content": content, "filepath": str(filepath)}
    except Exception:
        return {"status": "success", "content": content, "output": content, "filepath": str(filepath)}
