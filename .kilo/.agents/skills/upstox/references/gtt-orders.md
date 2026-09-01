# GTT (Good-Till-Triggered) Orders Reference

GTT orders rest until a price condition is met, then fire. They persist across
trading sessions. **All GTT methods live on `OrderApiV3` and take a request body.**
Signatures and the rule model are verified against the SDK's own examples.

## Concepts

- **`type`** — `"SINGLE"` (one entry leg) or `"MULTIPLE"` (entry + target + stop-loss, OCO-style).
- **`rules`** — a list of `GttRule`, each describing one leg.
- **`GttRule`** fields:
  - `strategy` — `"ENTRY"`, `"TARGET"`, or `"STOPLOSS"`
  - `trigger_type` — `"ABOVE"`, `"BELOW"`, or `"IMMEDIATE"`
  - `trigger_price` — float
  - `trailing_gap` — float, optional (trailing stop-loss; only on a `STOPLOSS` leg)
  - `market_protection` — int, optional
- **`product`** for GTT — only `"I"`, `"D"`, or `"MTF"`.

```python
import os, upstox_client
from upstox_client.rest import ApiException

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
order_v3 = upstox_client.OrderApiV3(upstox_client.ApiClient(configuration))
```

---

## Place Single-Leg GTT — `place_gtt_order(body)`

Fire one order when price crosses a trigger (e.g. buy-the-breakout / buy-the-dip).

```python
entry = upstox_client.GttRule(strategy="ENTRY", trigger_type="ABOVE", trigger_price=2600.0)

body = upstox_client.GttPlaceOrderRequest(
    type="SINGLE",
    instrument_token="NSE_EQ|INE002A01018",
    product="D",
    quantity=1,
    rules=[entry],
    transaction_type="BUY",
)
resp = order_v3.place_gtt_order(body=body)
print("GTT order:", resp.data)
```

Buy-the-dip uses `trigger_type="BELOW"`:

```python
entry = upstox_client.GttRule(strategy="ENTRY", trigger_type="BELOW", trigger_price=1400.0)
body = upstox_client.GttPlaceOrderRequest(
    type="SINGLE", instrument_token="NSE_EQ|INE009A01021",  # Infosys
    product="D", quantity=5, rules=[entry], transaction_type="BUY",
)
order_v3.place_gtt_order(body=body)
```

---

## Place Multi-Leg GTT (entry + target + stop-loss) — `place_gtt_order(body)`

A `MULTIPLE` GTT brackets a trade: an `ENTRY` leg arms it, then `TARGET` and
`STOPLOSS` legs become active (use `IMMEDIATE` so they evaluate once entry fills).

```python
entry    = upstox_client.GttRule(strategy="ENTRY",    trigger_type="ABOVE",     trigger_price=2600.0, market_protection=0)
target   = upstox_client.GttRule(strategy="TARGET",   trigger_type="IMMEDIATE", trigger_price=2750.0)
stoploss = upstox_client.GttRule(strategy="STOPLOSS", trigger_type="IMMEDIATE", trigger_price=2500.0)

body = upstox_client.GttPlaceOrderRequest(
    type="MULTIPLE",
    instrument_token="NSE_EQ|INE002A01018",
    product="D",
    quantity=1,
    rules=[entry, target, stoploss],
    transaction_type="BUY",
)
resp = order_v3.place_gtt_order(body=body)
```

### Trailing stop-loss

Add `trailing_gap` to the `STOPLOSS` leg — the stop trails the price by that gap:

```python
stoploss = upstox_client.GttRule(
    strategy="STOPLOSS", trigger_type="IMMEDIATE", trigger_price=2500.0, trailing_gap=3.0
)
```

---

## Modify GTT — `modify_gtt_order(body)`

Pass the existing `gtt_order_id`, the same `type`, the (possibly changed) `quantity`,
and the full new `rules` list.

```python
entry = upstox_client.GttRule(strategy="ENTRY", trigger_type="ABOVE", trigger_price=2620.0)

body = upstox_client.GttModifyOrderRequest(
    type="SINGLE",
    gtt_order_id="GTT-C25270200137952",
    rules=[entry],
    quantity=1,
)
resp = order_v3.modify_gtt_order(body=body)
```

## Cancel GTT — `cancel_gtt_order(body)`

```python
body = upstox_client.GttCancelOrderRequest(gtt_order_id="GTT-C250303008840")
resp = order_v3.cancel_gtt_order(body=body)
```

## Get GTT details — `get_gtt_order_details(gtt_order_id=...)`

```python
# One GTT order
resp = order_v3.get_gtt_order_details(gtt_order_id="GTT-C25030300128840")

# All GTT orders (omit the argument)
all_gtt = order_v3.get_gtt_order_details()
for g in all_gtt.data:
    print(g.gtt_order_id, g.trading_symbol, g.type, g.rules)
```
