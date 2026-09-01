"""
historical_candles.py — Fetch historical candles (v3) and print a quick summary.

Usage:
    UPSTOX_ACCESS_TOKEN=xxx python historical_candles.py
"""

import sys
import pathlib
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import upstox_client
from upstox_client.rest import ApiException
from scripts.upstox_helpers import get_client

INSTRUMENT = "NSE_EQ|INE002A01018"   # Reliance
UNIT = "days"                        # minutes | hours | days | weeks | months
INTERVAL = "1"                       # int valid for the unit (minutes 1-300, hours 1-5, else 1)


def main():
    hist = upstox_client.HistoryV3Api(get_client())
    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=30)).isoformat()

    try:
        # get_historical_candle_data1 is the SDK overload that accepts a
        # from_date/to_date range; get_historical_candle_data takes to_date only.
        resp = hist.get_historical_candle_data1(INSTRUMENT, UNIT, INTERVAL, to_date, from_date)
    except ApiException as e:
        print("Failed:", e.body)
        return

    candles = resp.data.candles
    if not candles:
        print("No candles returned.")
        return

    closes = [c[4] for c in candles]
    print(f"{INSTRUMENT}  {UNIT}/{INTERVAL}  {from_date} → {to_date}")
    print(f"Candles: {len(candles)}")
    print(f"Last close: {closes[0]:.2f}   period high: {max(c[2] for c in candles):.2f}   "
          f"period low: {min(c[3] for c in candles):.2f}")
    if len(closes) >= 20:
        print(f"20-period SMA: {sum(closes[:20]) / 20:.2f}")


if __name__ == "__main__":
    main()
