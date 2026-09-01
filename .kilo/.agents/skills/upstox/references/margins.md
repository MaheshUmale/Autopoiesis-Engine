# Margins, Funds & Charges Reference

> Verified: funds live on `UserApi`; margin and brokerage on `ChargeApi` (singular).
> The margin endpoint is `ChargeApi.post_margin(body)` with a `MarginRequest` that
> wraps a list of `Instrument`s — there is no `get_margin`.

```python
import os, upstox_client

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
client = upstox_client.ApiClient(configuration)
```

---

## Available funds & margin — `UserApi`

```python
user = upstox_client.UserApi(client)

# v3 — no arguments, returns both segments
funds = user.get_user_fund_margin_v3().data

# v2 — api_version required, optional segment filter (SEC = securities, COM = commodity)
funds_v2 = user.get_user_fund_margin(api_version="2.0", segment="SEC").data
```

`UserFundMarginData` fields (per segment): `available_margin`, `used_margin`,
`payin_amount`, `span_margin`, `adhoc_margin`, `exposure_margin`, `notional_cash`.

```python
for segment, d in funds.items():        # e.g. "equity", "commodity"
    print(segment, "available:", d.available_margin, "used:", d.used_margin)
```

---

## Required margin for orders — `ChargeApi.post_margin(body)`

`body` is a `MarginRequest(instruments=[Instrument(...)])`. Each `Instrument` has
`instrument_key`, `quantity`, `transaction_type`, `product`, `price`.

```python
charge = upstox_client.ChargeApi(client)

body = upstox_client.MarginRequest(instruments=[
    upstox_client.Instrument(
        instrument_key="NSE_FO|43885",
        quantity=75,                 # 1 lot — verify lot size first
        transaction_type="SELL",
        product="I",
        price=0.0,
    )
])
resp = charge.post_margin(body).data
print("Required margin:", resp.required_margin)
print("Final margin   :", resp.final_margin)
for m in resp.margins:               # per-instrument breakdown (Margin)
    print("  span:", m.span_margin, "exposure:", m.exposure_margin,
          "total:", m.total_margin)
```

---

## Brokerage & charges estimate — `ChargeApi.get_brokerage(...)`

```python
resp = charge.get_brokerage(
    instrument_token="NSE_EQ|INE002A01018",
    quantity=10,
    product="I",                 # I = intraday, D = delivery
    transaction_type="BUY",
    price=2500.0,
    api_version="2.0",
).data

print("Total charges:", resp.total)
print("Brokerage    :", resp.brokerage)
print("STT          :", resp.taxes.stt)
print("GST          :", resp.taxes.gst)
print("Stamp duty   :", resp.taxes.stamp_duty)
print("Transaction  :", resp.other_taxes.transaction)
print("SEBI turnover:", resp.other_taxes.sebi_turnover)
```

`BrokerageData`: `total`, `brokerage`, `taxes` (`gst`, `stt`, `stamp_duty`),
`other_taxes` (`transaction`, `clearing`, `sebi_turnover`), `dp_plan`.

---

## Pre-order check pattern

```python
def can_afford(user, charge, instrument_key, qty, product, transaction_type, price):
    funds = user.get_user_fund_margin_v3().data
    available = max(d.available_margin for d in funds.values())
    body = upstox_client.MarginRequest(instruments=[
        upstox_client.Instrument(instrument_key=instrument_key, quantity=qty,
                                 transaction_type=transaction_type, product=product, price=price)
    ])
    required = charge.post_margin(body).data.required_margin
    print(f"Available ₹{available:,.2f} | Required ₹{required:,.2f}")
    if required > available:
        print(f"⚠️  Short by ₹{required - available:,.2f}")
        return False
    return True
```
