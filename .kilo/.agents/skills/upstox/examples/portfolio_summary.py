"""
portfolio_summary.py — Holdings, open positions, and fund balance.

Usage:
    UPSTOX_ACCESS_TOKEN=xxx python portfolio_summary.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import upstox_client
from upstox_client.rest import ApiException
from scripts.upstox_helpers import get_client


def main():
    client = get_client()
    portfolio = upstox_client.PortfolioApi(client)
    user = upstox_client.UserApi(client)

    # ── Holdings ────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("HOLDINGS (delivery / long-term)")
    print("=" * 72)
    holdings = portfolio.get_holdings(api_version="2.0").data
    if not holdings:
        print("  None.")
    else:
        invested = sum(h.average_price * h.quantity for h in holdings)
        value = sum(h.last_price * h.quantity for h in holdings)
        print(f"{'Symbol':<16}{'Qty':>6}{'Avg':>10}{'LTP':>10}{'Value':>13}{'P&L':>13}{'%':>8}")
        print("-" * 72)
        for h in sorted(holdings, key=lambda x: -x.pnl):
            pct = (h.last_price - h.average_price) / h.average_price * 100 if h.average_price else 0
            print(f"{h.trading_symbol:<16}{h.quantity:>6}{h.average_price:>10.2f}"
                  f"{h.last_price:>10.2f}{h.last_price * h.quantity:>13,.2f}{h.pnl:>13,.2f}{pct:>7.2f}%")
        print("-" * 72)
        print(f"{'TOTAL':<16}{'':>6}{'':>10}{'':>10}{value:>13,.2f}{value - invested:>13,.2f}"
              f"{((value - invested) / invested * 100 if invested else 0):>7.2f}%")

    # ── Positions ───────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("OPEN POSITIONS (intraday / F&O)")
    print("=" * 72)
    positions = [p for p in portfolio.get_positions(api_version="2.0").data if p.quantity != 0]
    if not positions:
        print("  None.")
    else:
        print(f"{'Symbol':<22}{'Net Qty':>9}{'Avg':>10}{'LTP':>10}{'P&L':>13}")
        print("-" * 64)
        for p in positions:
            pnl = (p.realised or 0) + (p.unrealised or 0)
            print(f"{p.trading_symbol:<22}{p.quantity:>9}{p.average_price:>10.2f}"
                  f"{p.last_price:>10.2f}{pnl:>13,.2f}")

    # ── Funds ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("FUND BALANCE")
    print("=" * 72)
    try:
        funds = user.get_user_fund_margin_v3().data
        # v3 returns a structured object (available_to_trade / unavailable_to_trade),
        # not a per-segment dict like the v2 funds-and-margin API.
        avail = funds.available_to_trade
        cash = avail.cash_available_to_trade
        pledge = avail.pledge_available_to_trade
        used = 0.0
        if cash and cash.margin_used:
            used += cash.margin_used.total
        if pledge and pledge.margin_used:
            used += pledge.margin_used.total
        pledge_margin = pledge.margin_from_pledge.total if pledge and pledge.margin_from_pledge else 0.0
        print(f"  Available to trade  ₹{avail.total:>14,.2f}")
        print(f"  Cash available      ₹{(cash.total if cash else 0.0):>14,.2f}")
        print(f"  Pledge margin       ₹{pledge_margin:>14,.2f}")
        print(f"  Margin used         ₹{used:>14,.2f}")
    except ApiException as e:
        print("  Could not fetch funds:", e.body)
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
