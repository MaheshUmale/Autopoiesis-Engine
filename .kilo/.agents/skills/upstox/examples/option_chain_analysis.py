"""
option_chain_analysis.py — Nifty option chain: ATM strikes, PCR, and max pain.

Usage:
    UPSTOX_ACCESS_TOKEN=xxx python option_chain_analysis.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import upstox_client
from scripts.upstox_helpers import get_client

UNDERLYING = "NSE_INDEX|Nifty 50"
EXPIRY_DATE = "2026-06-09"     # set to a real expiry (see get_option_contracts)


def main():
    client = get_client()
    mq = upstox_client.MarketQuoteV3Api(client)
    options = upstox_client.OptionsApi(client)

    spot = list(mq.get_ltp(instrument_key=UNDERLYING).data.values())[0].last_price
    chain = options.get_put_call_option_chain(
        instrument_key=UNDERLYING, expiry_date=EXPIRY_DATE).data

    atm = min(chain, key=lambda s: abs(s.strike_price - spot))
    print(f"\n{'=' * 66}")
    print(f"  {UNDERLYING}   expiry {EXPIRY_DATE}   spot {spot:.2f}   ATM {atm.strike_price:.0f}")
    print(f"{'=' * 66}")

    print(f"\n{'CE IV':>7}{'CE OI':>12}{'CE LTP':>9} | {'Strike':^9} | {'PE LTP':>9}{'PE OI':>12}{'PE IV':>7}")
    print("-" * 66)
    for s in sorted((s for s in chain if abs(s.strike_price - atm.strike_price) <= 500),
                    key=lambda x: -x.strike_price):
        ce, pe = s.call_options, s.put_options
        mark = "  <ATM" if s.strike_price == atm.strike_price else ""
        print(f"{ce.option_greeks.iv:>6.1f}%{ce.market_data.oi:>12,.0f}{ce.market_data.ltp:>9.2f} | "
              f"{s.strike_price:^9.0f} | {pe.market_data.ltp:>9.2f}{pe.market_data.oi:>12,.0f}"
              f"{pe.option_greeks.iv:>6.1f}%{mark}")

    ce_oi = sum((s.call_options.market_data.oi or 0) for s in chain)
    pe_oi = sum((s.put_options.market_data.oi or 0) for s in chain)
    pcr = pe_oi / ce_oi if ce_oi else 0
    print(f"\nPCR: {pcr:.3f}  ({'bullish' if pcr > 1 else 'bearish'} bias)   "
          f"CE OI {ce_oi:,.0f} | PE OI {pe_oi:,.0f}")

    best, best_pain = None, float("inf")
    for k in (s.strike_price for s in chain):
        pain = sum(max(0, k - s.strike_price) * (s.call_options.market_data.oi or 0) +
                   max(0, s.strike_price - k) * (s.put_options.market_data.oi or 0)
                   for s in chain)
        if pain < best_pain:
            best, best_pain = k, pain
    print(f"Max pain: {best:.0f}  (spot {spot - best:+.0f} from max pain)\n")


if __name__ == "__main__":
    main()
