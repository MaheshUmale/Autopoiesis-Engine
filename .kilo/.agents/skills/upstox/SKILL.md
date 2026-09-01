---
name: upstox
description: >-
  Connects to a user's Upstox account through the official upstox-python-sdk to
  execute trades and pull live data from Indian exchanges (NSE, BSE, MCX). Covers
  the full workflow: resolving tradable instruments and
  running orders through safety checks before they go live. Reach for this skill
  to place, amend, or cancel orders; inspect holdings,
  positions, available funds, or margin requirements; pull last-traded price,
  OHLC, full quotes, historical candles, or option chains with greeks; calculate
  realised and unrealised P&L; or open a websocket feed for live market and
  portfolio updates. Relevant whenever a request involves Upstox, the Upstox API,
  Upstox orders or portfolios, or Indian equity, derivatives, and F&O trading on
  NSE, BSE, or MCX.
---

# Upstox Agent Skill

Trade on Upstox from an AI agent — place live orders, read portfolio data, stream
market feeds, and access the full Indian market universe across NSE, BSE, and MCX
through the [Upstox Developer API](https://upstox.com/developer/api-documentation/)
and the official `upstox-python-sdk`.

All SDK signatures in this skill and its references are verified against the
[upstox-python SDK source](https://github.com/upstox/upstox-python). The single
most common source of bugs is mixing up the v2 and v3 API classes — read the
**v2 vs v3** note below before writing order or quote code.

---

## Setup

### Install

```bash
pip install upstox-python-sdk
```

### Credentials — environment variables only, never hardcode

```bash
export UPSTOX_ACCESS_TOKEN="your-daily-access-token"
export UPSTOX_SANDBOX_ACCESS_TOKEN="your-sandbox-access-token"
```

### Initialize the client

```python
import os
import upstox_client

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
api_client = upstox_client.ApiClient(configuration)
```

Prefer the shared helper so every call reuses one configured client:

```python
from scripts.upstox_helpers import get_client
api_client = get_client()                 # reads UPSTOX_ACCESS_TOKEN (or sandbox)
```

### Sandbox (paper trading)

Use the sandbox to place test orders without real money. The SDK exposes a flag —
no separate base URL needed:

```python
configuration = upstox_client.Configuration(sandbox=True)
configuration.access_token = os.environ["UPSTOX_SANDBOX_ACCESS_TOKEN"]
```

`get_client(sandbox=True)` does the same. **Always rehearse order-placement
workflows in the sandbox before going live.**

### Base URL

`https://api.upstox.com/v2` (and `/v3` for newer endpoints — the SDK handles this per class).

---

## v2 vs v3 — read this before writing order/quote code

Upstox ships two generations of some APIs. They use **different SDK classes and
different method signatures**. Picking the wrong one is the #1 cause of errors.

| Concern | v3 (preferred) | v2 (legacy) |
|---------|----------------|-------------|
| Orders | `OrderApiV3` — `place_order(body)`, `modify_order(body)`, `cancel_order(order_id)` — **no `api_version` arg** | `OrderApi` — `place_order(body, api_version)`, etc. — **`api_version` required** |
| GTT orders | `OrderApiV3.place_gtt_order(body)` (only v3) | — |
| LTP / OHLC / greeks | `MarketQuoteV3Api` — `get_ltp(instrument_key=...)` — no `api_version` | `MarketQuoteApi` — `ltp(symbol, api_version)` |
| Historical candles | `HistoryV3Api.get_historical_candle_data(instrument_key, unit, interval, to_date, from_date=...)` | `HistoryApi` (older interval scheme) |
| Funds & margin | `UserApi.get_user_fund_margin_v3()` — no args | `UserApi.get_user_fund_margin(api_version, segment=...)` |

**Default to v3** for orders, quotes, and historical data. Multi-order, order book,
trades, brokerage, P&L, options, holidays, and convert-position remain on their v2
classes (`OrderApi`, `ChargeApi`, etc.).

---

## Safety Guardrails — ALWAYS ENFORCE

This skill can place **live, irreversible financial orders**. Before any
`place_order`, `modify_order`, `cancel_order`, `place_gtt_order`, `exit_positions`,
or `cancel_multi_order`:

| Rule | Behaviour |
|------|-----------|
| **Confirmation required** | Show a full, human-readable order preview and get explicit user confirmation before placing/modifying/cancelling. Run `scripts/validate_order.py` first. |
| **Default order type: LIMIT** | Never place a MARKET order unless the user explicitly asks for "market". |
| **Default quantity** | 1 share (equity) or 1 lot (F&O) when quantity is unspecified — never guess larger. |
| **Lot-size validation** | Reject F&O orders whose quantity is not a multiple of the instrument's `lot_size`. |
| **Market Price Protection** | MARKET orders are auto-bounded by Upstox MPP; pass `market_protection` (%) to set your own price buffer so a market order can't fill at a wild price. See `references/orders.md`. |
| **Kill switch** | A user can halt all trading in a segment via `UserApi.update_kill_switch([{segment, action}])` — `DISABLE` cancels pending orders and blocks new ones. Warn about the ~12-hour re-enable lock before disabling. See `references/kill-switch.md`. |
| **Sandbox first** | Rehearse in sandbox (`Configuration(sandbox=True)`) when the user is testing. |
| **No hardcoded secrets** | Always read tokens from `os.environ`. |

---

## Rate Limits

Breaching any limit returns HTTP `429 Too Many Requests` — back off before
retrying.

### Combined rate limiting for Order Placement APIs

Applies across Place, Modify, Cancel, Multi Order, and GTT Order — combined.

**Regular Algos** — no algo registration needed:

| Time duration | Request limit |
|---------------|---------------|
| Per second | 10 requests |
| Per minute | 500 requests |
| Per 30 minutes | 2000 requests |

**SEBI-Registered Algos** — algo registration needed:

| Time duration | Request limit |
|---------------|---------------|
| Per second | 50 requests |
| Per minute | 500 requests |
| Per 30 minutes | 2000 requests |

### Other Standard APIs

Holdings, positions, funds, historical candles, etc.

| Time duration | Request limit |
|---------------|---------------|
| Per second | 50 requests |
| Per minute | 500 requests |
| Per 30 minutes | 2000 requests |

---

## Key Constants

```python
# Transaction
BUY, SELL = "BUY", "SELL"

# Order types
MARKET, LIMIT, SL, SL_M = "MARKET", "LIMIT", "SL", "SL-M"

# Products
INTRADAY, DELIVERY, COVER, ONE_CANCELS_OTHER, MTF = "I", "D", "CO", "OCO", "MTF"

# Validity
DAY, IOC = "DAY", "IOC"
```

- **Exchanges** (the `exchange` field): `NSE`, `NFO`, `CDS`, `BSE`, `BFO`, `BCD`, `MCX`
- **`instrument_key` segment prefixes**: `NSE_EQ`, `NSE_FO`, `NSE_INDEX`, `BSE_EQ`, `BSE_FO`, `BSE_INDEX`, `NCD_FO`, `BCD_FO`, `MCX_FO`

### instrument_key format

```
SEGMENT|IDENTIFIER
"NSE_EQ|INE002A01018"     # Reliance (equity → ISIN)
"NSE_INDEX|Nifty 50"      # index (→ name)
"NSE_FO|43919"            # F&O (→ numeric exchange token)
```

Resolve human names to `instrument_key` with `scripts/instrument_search.py` (the
server-side Instrument Search API — no master-file downloads). **Always resolve
the `instrument_key` this way before placing an order**; do not guess
option/futures tokens — they change per expiry.

```python
from scripts.instrument_search import resolve_instrument_key
inst = resolve_instrument_key("Reliance", exchanges="NSE", segments="EQ")
instrument_token = inst["instrument_key"]   # pass inst["lot_size"] to validate_order for F&O
```

---

## Core Patterns

### Place a limit buy (v3)

```python
import os, upstox_client
from upstox_client.rest import ApiException

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
order_api = upstox_client.OrderApiV3(upstox_client.ApiClient(configuration))

body = upstox_client.PlaceOrderV3Request(
    quantity=1,
    product="D",                              # D = delivery/CNC
    validity="DAY",
    price=2500.0,
    tag="skill-order",
    instrument_token="NSE_EQ|INE002A01018",   # Reliance
    order_type="LIMIT",
    transaction_type="BUY",
    disclosed_quantity=0,
    trigger_price=0.0,
    is_amo=False,                             # required; True only for after-market orders
)

try:
    resp = order_api.place_order(body)        # NOTE: v3 has no api_version arg
    print("Order ID:", resp.data.order_ids)
except ApiException as e:
    print("Order failed:", e.body)
```

### Get holdings (v2 PortfolioApi)

```python
portfolio_api = upstox_client.PortfolioApi(upstox_client.ApiClient(configuration))
holdings = portfolio_api.get_holdings(api_version="2.0")
for h in holdings.data:
    print(h.trading_symbol, h.quantity, h.last_price, h.pnl)
```

### Get LTP (v3 MarketQuoteV3Api)

```python
mq = upstox_client.MarketQuoteV3Api(upstox_client.ApiClient(configuration))
resp = mq.get_ltp(instrument_key="NSE_EQ|INE002A01018")   # comma-separate for many
print(resp.data)
```

---

## Reference Index — load on demand

| Topic | When to load | File |
|-------|-------------|------|
| Orders (place/modify/cancel/multi/exit) | Any order operation | `references/orders.md` |
| GTT orders (single & multi-leg) | Conditional / good-till-triggered orders | `references/gtt-orders.md` |
| Portfolio (holdings, positions, convert, P&L) | View/manage portfolio | `references/portfolio.md` |
| Market data (LTP, OHLC, quotes, candles, status) | Prices & historical data | `references/market-data.md` |
| Option chain (greeks, OI, PCR, max pain) | Options analysis | `references/option-chain.md` |
| Margins, funds & brokerage charges | Pre-trade margin/charge checks | `references/margins.md` |
| Kill switch (halt trading in a segment) | Risk control / disable a segment | `references/kill-switch.md` |
| WebSocket (live ticks, order updates) | Streaming feeds | `references/websocket.md` |
| Instruments (resolve names → tokens, lot size) | Symbol lookup | `references/instruments.md` |
| Errors (HTTP & UDAPI codes) | Debugging, error codes, 429s | `references/errors.md` |

---

## Example Prompts This Skill Handles

- "Buy 10 SBIN at 820"
- "Place a GTT to buy Wipro when it falls to 440"
- "How much cash do I have free?"
- "Last price of Bank Nifty"
- "Pull the Nifty option chain for this week"

---

## SDK Reference

- **PyPI**: `upstox-python-sdk` · **Import**: `import upstox_client`
- **SDK source**: https://github.com/upstox/upstox-python
- **API docs**: https://upstox.com/developer/api-documentation/
- **Sandbox**: `upstox_client.Configuration(sandbox=True)`
- **Exceptions**: `from upstox_client.rest import ApiException`
