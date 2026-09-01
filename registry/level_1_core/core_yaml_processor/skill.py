def main(inputs: dict) -> dict:
    """Parse, query, and write YAML documents."""
    try:
        import yaml as _yaml
    except ImportError:
        return {"status": "error", "error": "PyYAML is not installed. Run: pip install pyyaml"}

    action = inputs.get("action", "read")
    file_path = inputs.get("file_path", "")
    query = inputs.get("query", "")
    data = inputs.get("data")

    if action == "read" and file_path:
        try:
            content = open(file_path, "r", encoding="utf-8").read()
            parsed = _yaml.safe_load(content)
            return {"status": "success", "data": parsed}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    if action == "write" and file_path and data is not None:
        try:
            from pathlib import Path
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                _yaml.dump(data, f, default_flow_style=False)
            return {"status": "success", "written_to": file_path}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    return {"status": "error", "error": f"Unsupported action: {action}"}
