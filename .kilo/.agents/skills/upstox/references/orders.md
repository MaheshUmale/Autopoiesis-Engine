# Orders Reference

> Signatures verified against the upstox-python SDK. **v3 order methods take NO
> `api_version` argument**; v2 methods do. Default to `OrderApiV3`.

```python
import os, upstox_client
from upstox_client.rest import ApiException

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
client = upstox_client.ApiClient(configuration)

order_v3 = upstox_client.OrderApiV3(client)   # place / modify / cancel / GTT
order_v2 = upstox_client.OrderApi(client)     # multi-order, order book, trades, exit
```

---

## Place Order — `OrderApiV3.place_order(body)`

`body` is a `PlaceOrderV3Request`. Fields:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `quantity` | int | ✅ | Shares/units (F&O: multiple of lot size) |
| `product` | str | ✅ | `I`, `D`, `CO`, `OCO`, `MTF` |
| `validity` | str | ✅ | `DAY` or `IOC` |
| `price` | float | ✅ | Limit price; `0` for MARKET |
| `instrument_token` | str | ✅ | e.g. `NSE_EQ\|INE002A01018` |
| `order_type` | str | ✅ | `MARKET`, `LIMIT`, `SL`, `SL-M` |
| `transaction_type` | str | ✅ | `BUY` or `SELL` |
| `trigger_price` | float | ✅ | For `SL`/`SL-M`; `0` otherwise |
| `disclosed_quantity` | int | ✅ | `0` if none |
| `is_amo` | bool | ✅ | Must be set (not `None`). `False` for normal orders; `True` only for after-market orders |
| `tag` | str | ❌ | Your label (≤ 40 chars) |
| `slice` | bool | ❌ | Auto-slice large orders into freeze-limit chunks. Optional for single `PlaceOrderV3Request`, but **required** (`False`/`True`) for `MultiOrderRequest` — see [Multiple Orders](#multiple-orders--ordermultiorderbody-v2-no-api_version) |
| `market_protection` | int | ❌ | Market Price Protection cap (%) — see below. Default `0` |

### Limit buy

```python
body = upstox_client.PlaceOrderV3Request(
    quantity=1, product="D", validity="DAY", price=2500.0, tag="skill-order",
    instrument_token="NSE_EQ|INE002A01018", order_type="LIMIT",
    transaction_type="BUY", disclosed_quantity=0, trigger_price=0.0, is_amo=False,
)
resp = order_v3.place_order(body)
print("Order IDs:", resp.data.order_ids)
```

### Market sell (intraday)

```python
body = upstox_client.PlaceOrderV3Request(
    quantity=5, product="I", validity="DAY", price=0, tag="intraday",
    instrument_token="NSE_EQ|INE040A01034", order_type="MARKET",
    transaction_type="SELL", disclosed_quantity=0, trigger_price=0.0, is_amo=False,
)
resp = order_v3.place_order(body)
```

### Stop-loss (SL — limit with trigger)

```python
body = upstox_client.PlaceOrderV3Request(
    quantity=10, product="I", validity="DAY",
    price=2480.0,          # limit price once triggered
    trigger_price=2490.0,  # price at which the SL activates
    tag="stoploss", instrument_token="NSE_EQ|INE002A01018",
    order_type="SL", transaction_type="SELL",
    disclosed_quantity=0, is_amo=False,
)
resp = order_v3.place_order(body)
```

---

## Market Price Protection (MPP)

MARKET orders never execute "at any price" on Upstox. Upstox **automatically**
converts protected market orders into limit orders bounded by a buffer around
the prevailing price (roughly 0.5%–25% depending on the instrument), so a thin
or fast-moving book can't fill you at a wild price. This applies automatically to
market orders on stock options, commodity options, and multi-position square-offs
— no field required.

To set your own buffer, pass `market_protection` (a percentage) on the order:

```python
body = upstox_client.PlaceOrderV3Request(
    quantity=5, product="I", validity="DAY", price=0, tag="protected",
    instrument_token="NSE_FO|43919", order_type="MARKET",
    transaction_type="BUY", disclosed_quantity=0, trigger_price=0.0, is_amo=False,
    market_protection=5,    # cap fills within 5% of the market price
)
resp = order_v3.place_order(body)
```

`market_protection=0` (default) leaves Upstox's automatic protection in place.

---

## Modify Order — `OrderApiV3.modify_order(body)`

`body` is a `ModifyOrderRequest` (there is **no** `ModifyOrderV3Request`).
Positional order: `(quantity, validity, price, order_id, order_type, disclosed_quantity, trigger_price)`.

```python
body = upstox_client.ModifyOrderRequest(
    20,          # quantity
    "DAY",       # validity
    2510.0,      # price
    "250121010502101",  # order_id
    "LIMIT",     # order_type
    0,           # disclosed_quantity
    0,           # trigger_price
    market_protection=0,
)
resp = order_v3.modify_order(body)
```

## Cancel Order — `OrderApiV3.cancel_order(order_id)`

```python
resp = order_v3.cancel_order("250121010502101")
print(resp.data.order_id)
```

---

## Multiple Orders — `OrderApi.place_multi_order(body)` (v2, no api_version)

`body` is a list of `MultiOrderRequest`. Each needs a unique `correlation_id`.

> ⚠️ **`slice` is required here.** Unlike `PlaceOrderV3Request` (where `slice` is
> optional), the `MultiOrderRequest` model raises
> `ValueError: Invalid value for 'slice', must not be 'None'` if you omit it.
> Pass `slice=False` for normal orders, or `slice=True` to auto-split a large
> order into freeze-limit chunks.

```python
orders = [
    upstox_client.MultiOrderRequest(
        quantity=1, product="D", validity="DAY", price=2500.0, tag="basket",
        slice=False,
        instrument_token="NSE_EQ|INE002A01018", order_type="LIMIT",
        transaction_type="BUY", disclosed_quantity=0, trigger_price=0.0,
        correlation_id="reliance-1",
    ),
    upstox_client.MultiOrderRequest(
        quantity=1, product="D", validity="DAY", price=1600.0, tag="basket",
        slice=False,
        instrument_token="NSE_EQ|INE040A01034", order_type="LIMIT",
        transaction_type="BUY", disclosed_quantity=0, trigger_price=0.0,
        correlation_id="hdfcbank-1",
    ),
]
resp = order_v2.place_multi_order(orders)
```

## Cancel / Exit in bulk — `OrderApi` (v2)

```python
# Cancel all open orders, optionally filtered by tag/segment
order_v2.cancel_multi_order(tag="basket")        # or: cancel_multi_order()

# Square off all open positions, optionally filtered
order_v2.exit_positions(tag="intraday")          # or: exit_positions()
```

> `exit_positions` and `cancel_multi_order` act broadly — always confirm scope
> with the user (and prefer a `tag`/`segment` filter) before calling.

---

## Read order & trade state — `OrderApi` (v2, api_version required)

```python
# Full order book for the day
book = order_v2.get_order_book(api_version="2.0")
for o in book.data:
    print(o.order_id, o.trading_symbol, o.status, o.quantity)

# Status / latest snapshot of one order
status = order_v2.get_order_status(order_id="250121010502101")

# Full lifecycle history of one order
hist = order_v2.get_order_details(api_version="2.0", order_id="250121010502101")
for ev in hist.data:
    print(ev.status, ev.status_message)

# Trades executed today (all)
trades = order_v2.get_trade_history(api_version="2.0")

# Trades for a specific order
otrades = order_v2.get_trades_by_order(order_id="250121010502101", api_version="2.0")
```

---

## Order Status Values

| Status | Meaning |
|--------|---------|
| `open` | Live at the exchange |
| `complete` | Fully executed |
| `cancelled` | Cancelled by user/system |
| `rejected` | Rejected — read `status_message` |
| `trigger pending` | SL/GTT trigger not yet hit |
