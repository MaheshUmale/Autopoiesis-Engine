def main(inputs: dict) -> dict:
    """Advanced CSV processor: read, filter, transform, aggregate, and write."""
    import csv
    import os
    from pathlib import Path

    file_path = inputs.get("file_path", "")
    action = inputs.get("action", "read")
    filter_col = inputs.get("filter_column")
    filter_val = inputs.get("filter_value")
    output_path = inputs.get("output_path", "")
    select_cols = inputs.get("select_columns", [])

    if not file_path or not Path(file_path).exists():
        return {"status": "error", "error": f"File not found: {file_path}"}

    rows = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if action == "read":
        return {"status": "success", "rows": rows, "count": len(rows)}

    if action == "filter":
        if not filter_col:
            return {"status": "error", "error": "filter_column required"}
        filtered = [r for r in rows if str(r.get(filter_col, "")) == str(filter_val)]
        return {"status": "success", "rows": filtered, "count": len(filtered)}

    if action == "aggregate":
        group_col = inputs.get("group_by", "")
        agg_col = inputs.get("aggregate_column", "")
        agg_op = inputs.get("aggregate_op", "sum")
        if not group_col or not agg_col:
            return {"status": "error", "error": "group_by and aggregate_column required"}
        groups: dict = {}
        for r in rows:
            key = r.get(group_col, "")
            groups.setdefault(key, []).append(float(r.get(agg_col, 0)))
        result = {}
        for k, vals in groups.items():
            if agg_op == "sum":
                result[k] = sum(vals)
            elif agg_op == "avg":
                result[k] = round(sum(vals) / len(vals), 4)
            elif agg_op == "count":
                result[k] = len(vals)
            else:
                result[k] = sum(vals)
        return {"status": "success", "aggregation": result}

    if action == "write" and output_path:
        if select_cols:
            rows = [{k: v for k, v in r.items() if k in select_cols} for r in rows]
        fieldnames = list(rows[0].keys()) if rows else []
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return {"status": "success", "written_to": output_path, "rows": len(rows)}

    return {"status": "error", "error": f"Unsupported action: {action}"}
