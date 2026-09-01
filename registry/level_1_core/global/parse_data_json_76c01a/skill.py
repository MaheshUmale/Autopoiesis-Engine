import json, os, csv

def main(inputs: dict) -> dict:
    """Autonomously synthesized micro-skill for: Parse data.json"""
    cwd = inputs.get("_cwd", os.getcwd())
    file_path = inputs.get("file_path", r"data.json")
    if not os.path.isabs(file_path):
        file_path = os.path.join(cwd, file_path)

    if "data" in inputs:
        return {"status": "success", "data": inputs["data"], "file_path": file_path}

    if not os.path.exists(file_path):
        return {"status": "error", "error": f"File not found: {file_path}"}
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        data = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                data.append([float(cell) if cell.replace('.', '', 1).replace('-', '', 1).isdigit() else cell for cell in row])
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    return {"status": "success", "data": data, "file_path": file_path}
