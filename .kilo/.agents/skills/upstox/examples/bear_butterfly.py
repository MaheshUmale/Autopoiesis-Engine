"""
bear_butterfly.py — Bear Put Butterfly (bearish, defined-risk).

Buys an ATM put, sells two ATM-1 puts, and buys an ATM-2 put on the same expiry.
Maximum profit is earned when the underlying closes near the middle strike
(ATM-1) at expiry. Net debit; risk is limited to the premium paid.

Legs (next weekly Nifty expiry):
    BUY  1 lot  ATM    PE
    SELL 2 lots ATM-1  PE
    BUY  1 lot  ATM-2  PE

Adapted from Upstox's official strategy examples, with token from env/config,
sandbox support, and an explicit confirmation before any live order.

Usage:
    UPSTOX_ACCESS_TOKEN=xxx python bear_butterfly.py
    # paper trade:
    UPSTOX_SANDBOX_ACCESS_TOKEN=xxx SANDBOX=1 python bear_butterfly.py
"""

import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import upstox_client
from upstox_client.rest import ApiException
from scripts.upstox_helpers import get_client

UNDERLYING = "Nifty 50"
EXCHANGE = "NSE"
EXPIRY = "next_week"
SANDBOX = bool(os.environ.get("SANDBOX"))

# (instrument_type, atm_offset, side, lots)
LEGS = [
    ("PE", 0, "BUY", 1),     # long  ATM put
    ("PE", -1, "SELL", 2),   # short 2x ATM-1 put (body)
    ("PE", -2, "BUY", 1),    # long  ATM-2 put
]


def resolve_legs(instruments):
    resolved = []
    for itype, offset, side, lots in LEGS:
        inst = instruments.search_instrument(
            UNDERLYING, exchanges=EXCHANGE, segments="FO",
            instrument_types=itype, expiry=EXPIRY, atm_offset=offset,
        ).data[0]
        resolved.append({
            "inst": inst, "side": side, "qty": inst["lot_size"] * lots,
        })
    return resolved


def preview(legs):
    print("\n" + "=" * 60)
    print("BEAR PUT BUTTERFLY")
    print("=" * 60)
    for leg in legs:
        print(f"  {leg['side']:4} {leg['qty']:>4} x {leg['inst']['trading_symbol']:24} "
              f"({leg['inst']['instrument_key']})")
    print("-" * 60)


def place(order_api, leg):
    return order_api.place_order(upstox_client.PlaceOrderV3Request(
        instrument_token=leg["inst"]["instrument_key"],
        quantity=leg["qty"], transaction_type=leg["side"],
        order_type="MARKET", product="D", validity="DAY",
        price=0, disclosed_quantity=0, trigger_price=0.0, is_amo=False,
        market_protection=-1,   # use exchange default Market Price Protection
    ))


def main():
    client = get_client(sandbox=SANDBOX)
    instruments = upstox_client.InstrumentsApi(client)
    order_api = upstox_client.OrderApiV3(client)

    try:
        legs = resolve_legs(instruments)
    except (ApiException, IndexError, KeyError) as e:
        print("Could not resolve option legs:", e)
        return

    preview(legs)
    print("Legs are placed sequentially as MARKET orders. If a later leg fails, "
          "earlier legs may already be live — square off manually.")
    if input("Place this butterfly? (yes/no): ").strip().lower() != "yes":
        print("Cancelled.")
        return

    for leg in legs:
        try:
            resp = place(order_api, leg)
            print(f"  {leg['side']} {leg['inst']['trading_symbol']} → {resp.data}")
        except ApiException as e:
            print(f"  {leg['side']} {leg['inst']['trading_symbol']} FAILED:", e.body)
            print("  Stopping. Review and square off any filled legs.")
            return


if __name__ == "__main__":
    main()
