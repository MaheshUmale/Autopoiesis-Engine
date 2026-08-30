def main(inputs: dict) -> dict:
    """Reads file contents as text or JSON object."""
    filepath = inputs.get("filepath", "")
    from pathlib import Path
    import json
    p = Path(filepath)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    raw_text = p.read_text(encoding="utf-8")
    try:
        data = json.loads(raw_text)
        return {"status": "success", "filepath": str(p.resolve()), "content": data, "format": "json"}
    except Exception:
        return {"status": "success", "filepath": str(p.resolve()), "content": raw_text, "format": "text"}
