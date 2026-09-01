def main(inputs: dict) -> dict:
    """Network diagnostics: DNS lookup, HTTP ping, and connectivity checks."""
    import socket
    import urllib.request

    target = inputs.get("target", "")
    port = int(inputs.get("port", 80))
    timeout = float(inputs.get("timeout", 5))
    results = {"target": target, "checks": []}

    if not target:
        return {"status": "error", "error": "target is required"}

    # DNS resolution
    try:
        ip = socket.gethostbyname(target)
        results["checks"].append({"check": "dns", "status": "success", "ip": ip})
    except Exception as e:
        results["checks"].append({"check": "dns", "status": "error", "error": str(e)})
        return {"status": "success", "results": results}

    # TCP connect
    try:
        with socket.create_connection((target, port), timeout=timeout):
            results["checks"].append({"check": "tcp", "status": "success", "port": port})
    except Exception as e:
        results["checks"].append({"check": "tcp", "status": "error", "error": str(e)})

    # HTTP HEAD
    try:
        req = urllib.request.Request(f"http://{target}:{port}", method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            results["checks"].append({"check": "http", "status": "success", "status_code": resp.status})
    except Exception as e:
        results["checks"].append({"check": "http", "status": "error", "error": str(e)})

    return {"status": "success", "results": results}
