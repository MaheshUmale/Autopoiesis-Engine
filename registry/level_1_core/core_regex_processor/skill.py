def main(inputs: dict) -> dict:
    """Regex processor: test, find, replace, and split text using patterns."""
    import re

    action = inputs.get("action", "test")
    pattern = inputs.get("pattern", "")
    text = inputs.get("text", "")
    replacement = inputs.get("replacement", "")
    flags = inputs.get("flags", 0)

    if not pattern:
        return {"status": "error", "error": "pattern is required"}
    if not text and action != "test":
        return {"status": "error", "error": "text is required"}

    compiled = re.compile(pattern, flags)

    if action == "test":
        return {"status": "success", "matched": bool(compiled.search(text))}

    if action == "find":
        matches = compiled.findall(text)
        return {"status": "success", "matches": matches, "count": len(matches)}

    if action == "replace":
        result, count = compiled.subn(replacement, text)
        return {"status": "success", "result": result, "replacements": count}

    if action == "split":
        parts = compiled.split(text)
        return {"status": "success", "parts": parts, "count": len(parts)}

    return {"status": "error", "error": f"Unsupported action: {action}"}
