# Portfolio Reference

> `PortfolioApi` methods take `api_version="2.0"`. Field names below are verified
> against the SDK models (`HoldingsData`, `PositionData`). Both `trading_symbol`
> and `tradingsymbol` attributes exist; this skill uses `trading_symbol`.

```python
import os, upstox_client

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
client = upstox_client.ApiClient(configuration)
portfolio = upstox_client.PortfolioApi(client)
```

---

## Holdings (long-term / delivery) — `get_holdings(api_version)`

```python
holdings = portfolio.get_holdings(api_version="2.0")
for h in holdings.data:
    print(h.trading_symbol, "Qty:", h.quantity, "Avg:", h.average_price,
          "LTP:", h.last_price, "P&L:", h.pnl, f"({h.day_change_percentage}% today)")
```

Key `HoldingsData` fields: `trading_symbol`, `instrument_token`, `isin`, `quantity`,
`t1_quantity`, `average_price`, `last_price`, `close_price`, `pnl`, `day_change`,
`day_change_percentage`, `company_name`, `collateral_quantity`, `haircut`, `product`, `exchange`.

---

## Positions (intraday / F&O) — `get_positions(api_version)`

```python
positions = portfolio.get_positions(api_version="2.0")
for p in positions.data:
    net_qty = p.quantity                       # +long / -short
    print(p.trading_symbol, "Net:", net_qty, "LTP:", p.last_price,
          "P&L:", (p.realised or 0) + (p.unrealised or 0))
```

Key `PositionData` fields: `trading_symbol`, `instrument_token`, `exchange`, `product`,
`quantity` (net), `multiplier`, `average_price`, `last_price`, `close_price`,
`buy_value`, `sell_value`, `realised`, `unrealised`, `pnl`, `value`, plus
`day_buy_quantity`/`day_sell_quantity`/`overnight_quantity` breakdowns.

MTF positions: `portfolio.get_mtf_positions()`.

---

## Convert Position (intraday ⇄ delivery) — `convert_positions(body, api_version)`

Convert an intraday (`I`) position to delivery (`D`) before square-off, or vice versa.

```python
body = upstox_client.ConvertPositionRequest(
    instrument_token="NSE_EQ|INE002A01018",
    new_product="D",          # convert TO
    old_product="I",          # convert FROM
    transaction_type="BUY",   # direction of the existing position
    quantity=1,
)
resp = portfolio.convert_positions(body, api_version="2.0")
```

---

## Portfolio summary (holdings value + P&L)

```python
def portfolio_summary(portfolio):
    holdings = portfolio.get_holdings(api_version="2.0").data
    if not holdings:
        print("No holdings.")
        return
    invested = sum(h.average_price * h.quantity for h in holdings)
    value    = sum(h.last_price * h.quantity for h in holdings)
    pnl      = sum(h.pnl for h in holdings)
    print(f"Invested : ₹{invested:,.2f}")
    print(f"Value    : ₹{value:,.2f}")
    print(f"P&L      : ₹{pnl:,.2f} ({pnl / invested * 100:.2f}%)\n")
    print(f"{'Symbol':<14}{'Qty':>6}{'Avg':>10}{'LTP':>10}{'P&L':>12}{'%':>8}")
    for h in sorted(holdings, key=lambda x: x.pnl, reverse=True):
        pct = (h.last_price - h.average_price) / h.average_price * 100 if h.average_price else 0
        print(f"{h.trading_symbol:<14}{h.quantity:>6}{h.average_price:>10.2f}"
              f"{h.last_price:>10.2f}{h.pnl:>12.2f}{pct:>7.2f}%")
```

---

## Realised P&L report — `TradeProfitAndLossApi`

Verified signatures. `segment` ∈ `EQ`, `FO`, `COM`, `CD`. `financial_year` is the
short form, e.g. `"2425"` for FY 2024-25. Optional `from_date`/`to_date` use
`dd-mm-yyyy`. Paginate using the metadata first.

```python
pnl_api = upstox_client.TradeProfitAndLossApi(client)

# 1. Metadata — trade count and page size
meta = pnl_api.get_trade_wise_profit_and_loss_meta_data(
    segment="EQ", financial_year="2425", api_version="2.0"
)

# 2. Paged trade-wise data
data = pnl_api.get_trade_wise_profit_and_loss_data(
    segment="EQ", financial_year="2425",
    page_number=1, page_size=500, api_version="2.0",
)
for t in data.data:
    print(t.scrip_name, t.quantity, t.buy_average, t.sell_average,
          t.buy_amount, t.sell_amount)

# 3. Aggregate charges for the period
charges = pnl_api.get_profit_and_loss_charges(
    segment="EQ", financial_year="2425", api_version="2.0"
)
```

`TradeWiseProfitAndLossData` fields: `scrip_name`, `isin`, `quantity`, `trade_type`
(`EQ`/`FUT`/`OPT`), `buy_date`, `buy_average`, `buy_amount`, `sell_date`,
`sell_average`, `sell_amount`.
