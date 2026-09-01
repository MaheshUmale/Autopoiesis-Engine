def main(inputs: dict) -> dict:
    """HTTP request client supporting GET/POST/PUT/DELETE with headers and body."""
    import urllib.request
    import json as _json
    url = inputs.get("url", "")
    method = inputs.get("method", "GET").upper()
    headers = inputs.get("headers", {})
    body = inputs.get("body")
    timeout = inputs.get("timeout", 30)

    if not url:
        return {"status": "error", "error": "Missing required parameter: url"}

    try:
        req = urllib.request.Request(url, method=method)
        for k, v in headers.items():
            req.add_header(k, str(v))
        data_bytes = None
        if body is not None:
            data_bytes = _json.dumps(body).encode("utf-8") if isinstance(body, (dict, list)) else str(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, data=data_bytes, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            try:
                resp_json = _json.loads(resp_body)
            except Exception:
                resp_json = resp_body
            return {
                "status": "success",
                "status_code": resp.status,
                "headers": dict(resp.headers),
                "body": resp_json,
            }
    except urllib.error.HTTPError as e:
        return {"status": "error", "status_code": e.code, "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
