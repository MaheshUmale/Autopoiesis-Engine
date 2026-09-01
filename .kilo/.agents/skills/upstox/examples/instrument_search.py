"""
instrument_search.py — Server-side instrument search via InstrumentsApi.

Two common uses:
  1. Free-text lookup (symbol / name / ISIN) → instrument_key.
  2. ATM-relative option lookup (e.g. the ATM Nifty call for next week's expiry),
     which is how the option-strategy examples resolve their legs.

Usage:
    UPSTOX_ACCESS_TOKEN=xxx python instrument_search.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import upstox_client
from upstox_client.rest import ApiException
from scripts.upstox_helpers import get_client, unwrap


def main():
    instruments = upstox_client.InstrumentsApi(get_client())

    try:
        # 1. Free-text equity search
        print("Equity search: 'Reliance'")
        eq = unwrap(instruments.search_instrument(
            "Reliance", exchanges="NSE", segments="EQ"))
        for inst in eq[:5]:
            print(f"  {inst['trading_symbol']:12} {inst['instrument_key']:24} "
                  f"lot={inst.get('lot_size')}")

        # 2. ATM-relative option lookup (next weekly Nifty expiry)
        print("\nNifty 50 options around ATM (next_week expiry):")
        for offset in (-1, 0, 1):
            ce = unwrap(instruments.search_instrument(
                "Nifty 50", exchanges="NSE", segments="FO",
                instrument_types="CE", expiry="next_week", atm_offset=offset))
            if ce:
                inst = ce[0]
                label = "ATM" if offset == 0 else f"ATM{offset:+d}"
                print(f"  {label:5} CE  {inst['trading_symbol']:22} "
                      f"strike={inst.get('strike_price')}  {inst['instrument_key']}")
    except ApiException as e:
        print("Search failed:", e.body)


if __name__ == "__main__":
    main()
