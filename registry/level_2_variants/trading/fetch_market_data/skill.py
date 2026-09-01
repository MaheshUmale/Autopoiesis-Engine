def main(inputs: dict) -> dict:
    """Variant skill for fetching OHLCV market data from a broker API (trading namespace)."""
    symbol = inputs.get("symbol", "")
    interval = inputs.get("interval", "1m")
    limit = inputs.get("limit", 100)

    if not symbol:
        return {"status": "error", "error": "symbol is required"}

    return {
        "status": "success",
        "candles": [],
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
        "note": "Replace with actual broker API integration."
    }
