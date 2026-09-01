"""
instrument_search.py — Resolve names / symbols to Upstox instrument_keys via the
server-side Instrument Search API.

No master files are downloaded. Everything goes through the authenticated
endpoint GET /v2/instruments/search (SDK: InstrumentsApi.search_instrument),
which also powers ATM-relative option lookup.

Docs: https://upstox.com/developer/api-documentation/instrument-search

Usage:
    python instrument_search.py "Reliance"
    python instrument_search.py "Nifty 50" --segments FO --type CE --expiry next_week --atm 0
    python instrument_search.py --resolve "Reliance"          # single best instrument_key
    python instrument_search.py --lot-size "Nifty 50"
"""

from __future__ import annotations

import argparse
import sys

try:                                   # works both as a module and run directly
    from .upstox_helpers import instruments_api, unwrap
except ImportError:                    # pragma: no cover
    from upstox_helpers import instruments_api, unwrap


def _as_dict(item) -> dict:
    """Search results come back as plain dicts; tolerate SDK model objects too."""
    if isinstance(item, dict):
        return item
    return item.to_dict() if hasattr(item, "to_dict") else dict(item)


def search(query: str, *, exchanges: str | None = None, segments: str | None = None,
           instrument_types: str | None = None, expiry: str | None = None,
           atm_offset: int | None = None, page_number: int | None = None,
           records: int | None = None, client=None) -> list[dict]:
    """Free-text instrument search. Returns a list of result dicts.

    query             symbol, company name, strike, or ISIN (<= 50 chars, required)
    exchanges         comma-separated: ALL, NSE, BSE, MCX        (default ALL)
    segments          comma-separated: ALL, EQ, FO, CURR, COMM, INDEX, OPT, FUT
    instrument_types  comma-separated: CE, PE, FUT, A, X, ...
    expiry            current_week / next_week / next_month / far_month / yyyy-MM-dd
    atm_offset        0 = ATM, +n strikes above, -n below (with expiry + type)
    records           1-30 per page (default 10)
    """
    kwargs = {
        "exchanges": exchanges, "segments": segments,
        "instrument_types": instrument_types, "expiry": expiry,
        "atm_offset": atm_offset, "page_number": page_number, "records": records,
    }
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    resp = instruments_api(client).search_instrument(query, **kwargs)
    return [_as_dict(i) for i in (unwrap(resp) or [])]


def search_equity(query: str, exchange: str = "NSE", client=None) -> list[dict]:
    """Search equities by company name or trading symbol."""
    return search(query, exchanges=exchange, segments="EQ", client=client)


def find_option(underlying: str, expiry: str, option_type: str,
                atm_offset: int = 0, exchange: str = "NSE", client=None) -> dict | None:
    """Return one option (ATM-relative) for an underlying + expiry.

    expiry      keyword (e.g. next_week) or yyyy-MM-dd
    option_type CE or PE
    atm_offset  0 = ATM, +1 = one strike OTM-side, -1 = one below
    """
    hits = search(underlying, exchanges=exchange, segments="FO",
                  instrument_types=option_type.upper(), expiry=expiry,
                  atm_offset=atm_offset, client=client)
    return hits[0] if hits else None


def resolve_instrument_key(query: str, *, exchanges: str | None = None,
                           segments: str | None = None, client=None,
                           **kwargs) -> dict:
    """Resolve a free-text query to a single best instrument.

    Returns the full result dict (with instrument_key, lot_size, tick_size, ...).
    Raises ValueError if nothing matches; if several match, returns the first and
    leaves disambiguation to the caller (inspect the 'candidates' it logs).
    """
    hits = search(query, exchanges=exchanges, segments=segments, client=client, **kwargs)
    if not hits:
        raise ValueError(f"No instrument found for query {query!r}.")
    return hits[0]


def get_lot_size(query: str, exchange: str = "NSE", client=None) -> int:
    """Return the F&O lot size for an underlying (resolved via search)."""
    hits = search(query, exchanges=exchange, segments="FO", client=client)
    for h in hits:
        if h.get("lot_size"):
            return int(h["lot_size"])
    raise ValueError(f"No F&O lot size found for {query!r}.")


def _print(rows: list[dict]) -> None:
    cols = ["instrument_key", "trading_symbol", "name", "segment",
            "strike_price", "instrument_type", "expiry", "lot_size", "isin"]
    present = [c for c in cols if any(r.get(c) not in (None, "") for r in rows)]
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in present}
    print("  ".join(c.ljust(widths[c]) for c in present))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in present))


def main() -> None:
    p = argparse.ArgumentParser(description="Search Upstox instruments (server-side API)")
    p.add_argument("query", help="Company name, symbol, strike, or ISIN")
    p.add_argument("--exchanges", help="ALL, NSE, BSE, MCX (comma-separated)")
    p.add_argument("--segments", help="ALL, EQ, FO, CURR, COMM, INDEX, OPT, FUT")
    p.add_argument("--type", dest="instrument_types", help="CE, PE, FUT, ... (comma-separated)")
    p.add_argument("--expiry", help="current_week/next_week/next_month/far_month or yyyy-MM-dd")
    p.add_argument("--atm", dest="atm_offset", type=int, help="ATM offset: 0=ATM, +n, -n")
    p.add_argument("--records", type=int, help="Records per page (1-30)")
    p.add_argument("--resolve", action="store_true", help="Print the single best instrument_key")
    p.add_argument("--lot-size", action="store_true", help="Print F&O lot size and exit")
    args = p.parse_args()

    if args.lot_size:
        print(get_lot_size(args.query, args.exchanges or "NSE"))
        return

    rows = search(args.query, exchanges=args.exchanges, segments=args.segments,
                  instrument_types=args.instrument_types, expiry=args.expiry,
                  atm_offset=args.atm_offset, records=args.records)
    if not rows:
        print(f"No instruments found for: {args.query}")
        sys.exit(1)

    if args.resolve:
        print(rows[0]["instrument_key"])
        return
    _print(rows)


if __name__ == "__main__":
    main()
