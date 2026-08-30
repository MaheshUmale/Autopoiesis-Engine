def main(inputs: dict) -> dict:
    """Converts structured dictionary or JSON data into a Parquet binary file."""
    data = inputs.get("data", {})
    output_path = inputs.get("output_path", "data.parquet")
    import pyarrow as pa
    import pyarrow.parquet as pq
    import json
    from pathlib import Path

    raw_json = json.dumps(data)
    schema = pa.schema([('data', pa.string())])
    table = pa.Table.from_batches([
        pa.RecordBatch.from_arrays([pa.array([raw_json])], schema=schema)
    ])
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, str(p))
    return {"status": "success", "parquet_path": str(p.resolve())}
