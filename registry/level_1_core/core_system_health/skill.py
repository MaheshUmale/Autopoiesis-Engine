def main(inputs: dict) -> dict:
    """System health check: CPU, memory, disk usage (best-effort cross-platform)."""
    import shutil
    import os
    health = {
        "platform": os.name,
        "cwd": os.getcwd(),
        "disk_usage": {},
    }
    try:
        usage = shutil.disk_usage(os.getcwd())
        health["disk_usage"] = {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent_used": round(usage.used / usage.total * 100, 1),
        }
    except Exception as e:
        health["disk_error"] = str(e)
    return {"status": "success", "health": health}
