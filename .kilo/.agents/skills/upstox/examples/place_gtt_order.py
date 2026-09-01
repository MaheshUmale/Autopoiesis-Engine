"""
place_gtt_order.py — Place a single-leg GTT (good-till-triggered) order.

Buys when the price crosses a trigger. Confirms before sending. GTT supports
products I, D, MTF only.

Usage:
    UPSTOX_ACCESS_TOKEN=xxx python place_gtt_order.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import upstox_client
from upstox_client.rest import ApiException
from scripts.upstox_helpers import get_client

INSTRUMENT = "NSE_EQ|INE002A01018"   # Reliance
TRANSACTION_TYPE = "BUY"
PRODUCT = "D"
QUANTITY = 1
TRIGGER_TYPE = "ABOVE"               # ABOVE | BELOW | IMMEDIATE
TRIGGER_PRICE = 2600.0


def main():
    print(f"GTT: {TRANSACTION_TYPE} {QUANTITY} of {INSTRUMENT} when price goes "
          f"{TRIGGER_TYPE} {TRIGGER_PRICE} (product {PRODUCT})")
    if input("Place this GTT order? (yes/no): ").strip().lower() != "yes":
        print("Cancelled.")
        return

    order_v3 = upstox_client.OrderApiV3(get_client())
    entry = upstox_client.GttRule(
        strategy="ENTRY", trigger_type=TRIGGER_TYPE, trigger_price=TRIGGER_PRICE)
    body = upstox_client.GttPlaceOrderRequest(
        type="SINGLE", instrument_token=INSTRUMENT, product=PRODUCT,
        quantity=QUANTITY, rules=[entry], transaction_type=TRANSACTION_TYPE)

    try:
        resp = order_v3.place_gtt_order(body=body)
        print("GTT placed:", resp.data)
    except ApiException as e:
        print("GTT failed:", e.body)


if __name__ == "__main__":
    main()
