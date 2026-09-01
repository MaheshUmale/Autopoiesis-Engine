def main(inputs: dict) -> dict:
    """File watcher: lists files in a directory with metadata and optional filtering."""
    import os
    from pathlib import Path
    from datetime import datetime

    dir_path = inputs.get("dir_path", ".")
    pattern = inputs.get("pattern", "*")
    recursive = inputs.get("recursive", False)

    base = Path(dir_path)
    if not base.exists() or not base.is_dir():
        return {"status": "error", "error": f"Directory not found: {dir_path}"}

    files = []
    glob_fn = base.rglob if recursive else base.glob
    for f in glob_fn(pattern):
        if f.is_file():
            stat = f.stat()
            files.append({
                "name": f.name,
                "path": str(f.resolve()),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    files.sort(key=lambda x: x["modified"], reverse=True)
    return {"status": "success", "files": files, "count": len(files)}
