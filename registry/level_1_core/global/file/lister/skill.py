import os

def main(inputs: dict) -> dict:
    """Lists directory items, sizes, and file metadata."""
    directory = inputs.get("directory", inputs.get("payload", "."))
    if not os.path.exists(str(directory)):
        return {"status": "error", "error": f"Directory not found: {directory}"}
    items = os.listdir(str(directory))
    return {"status": "success", "directory": str(directory), "items": items}
