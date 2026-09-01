def main(inputs: dict) -> dict:
    """Data visualization generator: returns JSON chart spec for Plotly/Chart.js rendering."""
    chart_type = inputs.get("chart_type", "bar")
    data = inputs.get("data", [])
    labels = inputs.get("labels", [])
    title = inputs.get("title", "Chart")
    x_label = inputs.get("x_label", "X")
    y_label = inputs.get("y_label", "Y")

    if not data and not labels:
        return {"status": "error", "error": "data or labels is required"}

    spec = {
        "type": chart_type,
        "data": {
            "labels": labels,
            "datasets": [{"label": title, "data": data}],
        },
        "options": {
            "plugins": {"title": {"display": True, "text": title}},
            "scales": {
                "x": {"title": {"display": True, "text": x_label}},
                "y": {"title": {"display": True, "text": y_label}},
            },
        },
    }
    return {"status": "success", "chart_spec": spec}
