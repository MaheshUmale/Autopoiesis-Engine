"""
market_quote.py — Fetch full market quotes (OHLC + depth + OI) for one or more
instruments.

Full quotes live on the v2 `MarketQuoteApi` (api_version required) and return a
complete snapshot — last price, OHLC, volume, circuit limits, total buy/sell
quantity, and the top-5 bid/ask depth. Up to 500 instruments per call.

Usage:
    UPSTOX_ACCESS_TOKEN=xxx python market_quote.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import upstox_client
from upstox_client.rest import ApiException
from scripts.upstox_helpers import get_client, unwrap

# Comma-separate up to 500 instrument keys
INSTRUMENTS = "NSE_EQ|INE002A01018,NSE_INDEX|Nifty 50"


def main():
    mq = upstox_client.MarketQuoteApi(get_client())
    try:
        resp = mq.get_full_market_quote(symbol=INSTRUMENTS, api_version="2.0")
    except ApiException as e:
        print("Quote fetch failed:", e.body)
        return

    for key, q in unwrap(resp).items():
        print("\n" + "=" * 52)
        print(f"{getattr(q, 'symbol', key)}  ({key})")
        print("-" * 52)
        print(f"  LTP            : {q.last_price}")
        if getattr(q, "ohlc", None):
            print(f"  OHLC           : {q.ohlc.open} / {q.ohlc.high} / "
                  f"{q.ohlc.low} / {q.ohlc.close}")
        print(f"  Net change     : {getattr(q, 'net_change', 'n/a')}")
        print(f"  Volume         : {getattr(q, 'volume', 'n/a')}")
        if getattr(q, "oi", None) is not None:
            print(f"  Open interest  : {q.oi}")
        depth = getattr(q, "depth", None)
        if depth and depth.buy and depth.sell:
            print(f"  Top bid / ask  : {depth.buy[0].price} x {depth.buy[0].quantity}"
                  f"   |   {depth.sell[0].price} x {depth.sell[0].quantity}")


if __name__ == "__main__":
    main()
