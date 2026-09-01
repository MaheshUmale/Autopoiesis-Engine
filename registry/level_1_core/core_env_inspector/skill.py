def main(inputs: dict) -> dict:
    """Detailed environment inspection: PATH, variables, OS info, Python env."""
    import os
    import sys
    import platform
    result = {
        "os": platform.system(),
        "os_version": platform.version(),
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "env_vars_count": len(os.environ),
        "path_dirs": os.environ.get("PATH", "").split(os.pathsep)[:20],
        "home": os.path.expanduser("~"),
        "temp": os.environ.get("TEMP", os.environ.get("TMP", "/tmp")),
    }
    filter_vars = inputs.get("filter_vars", [])
    if filter_vars:
        result["filtered_env"] = {k: v for k, v in os.environ.items() if k in filter_vars}
    return {"status": "success", "environment": result}
