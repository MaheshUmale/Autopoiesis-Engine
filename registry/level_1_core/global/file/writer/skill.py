def main(inputs: dict) -> dict:
    """Writes text or JSON content to a specified filepath."""
    filepath = inputs.get("filepath", "output.json")
    content = inputs.get("content", "")
    import json
    from pathlib import Path
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, (dict, list)):
        p.write_text(json.dumps(content, indent=2), encoding="utf-8")
    else:
        p.write_text(str(content), encoding="utf-8")
    return {"status": "success", "filepath": str(p.resolve())}
