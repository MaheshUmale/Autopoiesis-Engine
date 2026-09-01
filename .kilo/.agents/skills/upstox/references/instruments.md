# Instruments Reference

> Resolve instruments with the **server-side Instrument Search API** — do **not**
> download the gzipped master files. The search endpoint returns the same fields
> on demand and supports ATM-relative option lookup.
> Docs: https://upstox.com/developer/api-documentation/instrument-search

## instrument_key format

```
SEGMENT|IDENTIFIER
"NSE_EQ|INE002A01018"     # equity → ISIN
"NSE_INDEX|Nifty 50"      # index  → name
"NSE_FO|43919"            # F&O    → numeric exchange token
"MCX_FO|434855"           # commodity future
```

Always use `instrument_key` (unique, persistent) in API calls — not `exchange_token`.
**Resolve it via the search API before every order; never hardcode or guess
option/futures tokens — they change per expiry.**

---

## Instrument Search API — `InstrumentsApi.search_instrument`

`GET /v2/instruments/search` (bearer auth). Free-text search over symbol, name,
strike, or ISIN; no master-file download.

```python
import upstox_client

instruments = upstox_client.InstrumentsApi(client)

# Free-text search (symbol, name, ISIN, strike)
res = instruments.search_instrument("Reliance", exchanges="NSE", segments="EQ")
for inst in res.data:                       # res.data is a list of dicts
    print(inst["trading_symbol"], inst["instrument_key"], inst.get("lot_size"))

# ATM-relative option lookup — the ATM call for next week's Nifty expiry
atm_call = instruments.search_instrument(
    "Nifty 50", exchanges="NSE", segments="FO",
    instrument_types="CE", expiry="next_week", atm_offset=0,
).data[0]
# atm_offset=+1 → one strike OTM (call), -1 → one strike below, etc.
```

| Param | Values |
|-------|--------|
| `query` | Free text, ≤ 50 chars: symbol, name, strike, or ISIN (required) |
| `exchanges` | `ALL`, `NSE`, `BSE`, `MCX` (default `ALL`) |
| `segments` | `ALL`, `EQ`, `FO`, `CURR`, `COMM`, `INDEX`, `OPT`, `FUT` |
| `instrument_types` | `CE`, `PE`, `FUT`, `A`, `X` (comma-separated) |
| `expiry` | `current_week`, `next_week`, `next_month`, `far_month`, or `yyyy-MM-dd` |
| `atm_offset` | `0` = ATM, `+n` above, `-n` below the ATM strike |
| `page_number` | ≥ 1 (default 1) · `records` 1–30 per page (default 10) |

Each result includes `name`, `trading_symbol`, `instrument_key`, `exchange`,
`segment`, `instrument_type`, `lot_size`, `tick_size`, `freeze_quantity`,
`qty_multiplier`; F&O adds `expiry`, `strike_price`, `underlying_symbol`,
`weekly`; equity adds `isin`, `short_name`, `security_type`.

Response envelope:

```json
{ "status": "success",
  "data": [ { "instrument_key": "...", "trading_symbol": "...", "lot_size": 1, ... } ],
  "meta_data": { "page": { "page_number": 1, "total_pages": 1, "records": 10, "total_records": 1 } } }
```

---

## `scripts/instrument_search.py`

Wraps the endpoint with convenience helpers and a CLI (uses `get_client()` for
auth). No downloads, no caching of master files.

```python
from scripts.instrument_search import (
    search, search_equity, find_option, resolve_instrument_key, get_lot_size)

# Single best match for an order (returns the full dict)
inst = resolve_instrument_key("Reliance", exchanges="NSE", segments="EQ")
token, lot = inst["instrument_key"], inst.get("lot_size")

# ATM-relative option in one call
opt = find_option("Nifty 50", expiry="next_week", option_type="CE", atm_offset=0)

# F&O lot size for an underlying
lot = get_lot_size("Nifty 50")
```

CLI:

```bash
python scripts/instrument_search.py "Reliance" --segments EQ
python scripts/instrument_search.py "Nifty 50" --segments FO --type CE --expiry next_week --atm 0
python scripts/instrument_search.py --resolve "Reliance"      # prints the instrument_key
python scripts/instrument_search.py --lot-size "Nifty 50"
```
