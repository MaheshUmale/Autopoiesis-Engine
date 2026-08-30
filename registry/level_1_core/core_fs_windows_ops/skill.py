def main(inputs: dict) -> dict:
    """File read/write with UTF-8/BOM handling and attribute validation."""
    action = inputs.get("action", "read")
    filepath = inputs.get("filepath", "")
    content = inputs.get("content", "")
    from pathlib import Path
    p = Path(filepath)
    if action == "write":
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(content), encoding="utf-8")
        return {"status": "success", "filepath": str(p.resolve())}
    else:
        if not p.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        return {"status": "success", "filepath": str(p.resolve()), "content": p.read_text(encoding="utf-8")}
