# Option Chain Reference

> The option chain method is `OptionsApi.get_put_call_option_chain(instrument_key,
> expiry_date)` — **no `api_version`**. Each row is an `OptionStrikeData` with
> `strike_price`, `pcr`, `call_options`, `put_options`; each side is a
> `PutCallOptionChainData` with `.market_data` and `.option_greeks`. Verified.

```python
import os, upstox_client

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
client = upstox_client.ApiClient(configuration)
options = upstox_client.OptionsApi(client)
```

## Available expiries — `get_option_contracts(instrument_key)`

```python
contracts = options.get_option_contracts(instrument_key="NSE_INDEX|Nifty 50")
expiries = sorted({c.expiry for c in contracts.data})
print("Expiries:", expiries)
```

## Fetch the chain — `get_put_call_option_chain(instrument_key, expiry_date)`

```python
chain = options.get_put_call_option_chain(
    instrument_key="NSE_INDEX|Nifty 50",
    expiry_date="2025-01-30",     # YYYY-MM-DD, from get_option_contracts
).data

for s in chain:
    ce, pe = s.call_options, s.put_options
    print(f"{s.strike_price:>8.0f} | "
          f"CE {ce.market_data.ltp:>8.2f} IV {ce.option_greeks.iv:>5.1f} OI {ce.market_data.oi:>10,.0f} | "
          f"PE {pe.market_data.ltp:>8.2f} IV {pe.option_greeks.iv:>5.1f} OI {pe.market_data.oi:>10,.0f}")
```

### Fields

`market_data`: `ltp`, `volume`, `oi`, `prev_oi`, `close_price`, `bid_price`, `bid_qty`,
`ask_price`, `ask_qty`.
`option_greeks`: `delta`, `gamma`, `theta`, `vega`, `iv`, plus `pop` where available.
`OptionStrikeData` also exposes `pcr`, `underlying_key`, `underlying_spot_price`.

---

## Common index instrument keys

```python
NIFTY_50   = "NSE_INDEX|Nifty 50"
NIFTY_BANK = "NSE_INDEX|Nifty Bank"
NIFTY_FIN  = "NSE_INDEX|Nifty Fin Service"
SENSEX     = "BSE_INDEX|SENSEX"
BANKEX     = "BSE_INDEX|BANKEX"
```

---

## ATM strike finder

```python
def find_atm(options, mq_v3, instrument_key, expiry_date):
    spot = list(mq_v3.get_ltp(instrument_key=instrument_key).data.values())[0].last_price
    chain = options.get_put_call_option_chain(
        instrument_key=instrument_key, expiry_date=expiry_date).data
    atm = min(chain, key=lambda s: abs(s.strike_price - spot))
    print(f"Spot {spot:.2f}  ATM {atm.strike_price}")
    print(f"  CE {atm.call_options.market_data.ltp:.2f}  delta {atm.call_options.option_greeks.delta:.3f}")
    print(f"  PE {atm.put_options.market_data.ltp:.2f}  delta {atm.put_options.option_greeks.delta:.3f}")
    return atm

mq_v3 = upstox_client.MarketQuoteV3Api(client)
find_atm(options, mq_v3, "NSE_INDEX|Nifty 50", "2025-01-30")
```

## Put-Call Ratio (PCR)

```python
def pcr(options, instrument_key, expiry_date):
    chain = options.get_put_call_option_chain(
        instrument_key=instrument_key, expiry_date=expiry_date).data
    ce_oi = sum((s.call_options.market_data.oi or 0) for s in chain)
    pe_oi = sum((s.put_options.market_data.oi or 0) for s in chain)
    ratio = pe_oi / ce_oi if ce_oi else 0
    print(f"CE OI {ce_oi:,.0f}  PE OI {pe_oi:,.0f}  PCR {ratio:.3f} "
          f"({'bullish' if ratio > 1 else 'bearish'})")
    return ratio
```

## Max pain

```python
def max_pain(options, instrument_key, expiry_date):
    chain = options.get_put_call_option_chain(
        instrument_key=instrument_key, expiry_date=expiry_date).data
    strikes = [s.strike_price for s in chain]
    best, best_pain = None, float("inf")
    for k in strikes:
        pain = sum(max(0, k - s.strike_price) * (s.call_options.market_data.oi or 0) +
                   max(0, s.strike_price - k) * (s.put_options.market_data.oi or 0)
                   for s in chain)
        if pain < best_pain:
            best, best_pain = k, pain
    print(f"Max pain strike: {best}")
    return best
```
