def main(inputs: dict) -> dict:
    """Lists directory contents and metadata tree."""
    dirpath = inputs.get("dirpath", ".")
    from pathlib import Path
    p = Path(dirpath)
    if not p.exists():
        raise FileNotFoundError(f"Directory not found: {dirpath}")
    items = []
    for item in p.iterdir():
        items.append({
            "name": item.name,
            "is_dir": item.is_dir(),
            "size_bytes": item.stat().st_size if item.is_file() else 0
        })
    return {"status": "success", "dirpath": str(p.resolve()), "items": items}
