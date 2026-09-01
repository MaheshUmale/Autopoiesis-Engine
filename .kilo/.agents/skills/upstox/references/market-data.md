# Market Data Reference

> Prefer the **v3** classes. `MarketQuoteV3Api` and `HistoryV3Api` methods take **no
> `api_version`**. The v2 `MarketQuoteApi`/`HistoryApi` exist but use a different
> interval scheme. All signatures verified against the SDK.

```python
import os, upstox_client

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
client = upstox_client.ApiClient(configuration)
```

---

## Live quotes — `MarketQuoteV3Api`

```python
mq = upstox_client.MarketQuoteV3Api(client)

# LTP — pass instrument_key (comma-separate for many)
ltp = mq.get_ltp(instrument_key="NSE_EQ|INE002A01018,NSE_INDEX|Nifty 50")
print(ltp.data)   # dict keyed by instrument; each has .last_price, .cp, .volume, .ltq

# OHLC — interval is positional: I1, I5, I15, I30, 1d, 1w, 1M (intraday "I"+minutes, or day/week/month)
ohlc = mq.get_market_quote_ohlc(interval="1d", instrument_key="NSE_EQ|INE002A01018")

# Option greeks (LTP + iv/delta/gamma/theta/vega/oi)
greeks = mq.get_market_quote_option_greek(instrument_key="NSE_FO|43885")
```

### Full market quote (OHLC + depth) — v2 `MarketQuoteApi`

The full quote with market depth is on the v2 class (`api_version` required):

```python
mq_v2 = upstox_client.MarketQuoteApi(client)
full = mq_v2.get_full_market_quote(symbol="NSE_EQ|INE002A01018", api_version="2.0")
q = list(full.data.values())[0]
print("OHLC:", q.ohlc.open, q.ohlc.high, q.ohlc.low, q.ohlc.close)
print("LTP:", q.last_price, "Volume:", q.volume, "OI:", q.oi)
print("Top bid:", q.depth.buy[0].price, "x", q.depth.buy[0].quantity)
print("Top ask:", q.depth.sell[0].price, "x", q.depth.sell[0].quantity)
```

---

## Historical candles — `HistoryV3Api`

`get_historical_candle_data(instrument_key, unit, interval, to_date, from_date=...)`

- `unit` ∈ `minutes`, `hours`, `days`, `weeks`, `months`
- `interval` is an **int as a string/number** valid for the unit:
  - `minutes`: 1–300 · `hours`: 1–5 · `days`/`weeks`/`months`: 1
- dates are `YYYY-MM-DD`. `from_date` is optional (omit for the max default look-back).

```python
hist = upstox_client.HistoryV3Api(client)

# 5-minute candles for a date range
resp = hist.get_historical_candle_data(
    "NSE_EQ|INE002A01018", "minutes", "5", "2025-01-10", "2025-01-06"
)

# Daily candles
resp = hist.get_historical_candle_data(
    "NSE_EQ|INE002A01018", "days", "1", "2025-01-31", "2025-01-01"
)

for candle in resp.data.candles:
    ts, o, h, l, c, vol, oi = candle    # [timestamp, open, high, low, close, volume, oi]
    print(ts, o, h, l, c, vol)
```

### Intraday (today) — `get_intra_day_candle_data(instrument_key, unit, interval)`

```python
resp = hist.get_intra_day_candle_data("NSE_EQ|INE002A01018", "minutes", "1")
```

---

## Market status, timings & holidays — `MarketHolidaysAndTimingsApi`

> Class is `MarketHolidaysAndTimingsApi` (not `MarketInformationApi`).

```python
mkt = upstox_client.MarketHolidaysAndTimingsApi(client)

mkt.get_market_status(exchange="NSE")     # OPEN / CLOSED / PRE_OPEN ...
mkt.get_exchange_timings(_date="2025-01-15")
mkt.get_holidays()                         # all holidays
mkt.get_holiday(_date="2025-01-26")        # holiday(s) on a date
```
