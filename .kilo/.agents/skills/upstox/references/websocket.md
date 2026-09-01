# WebSocket Reference

Upstox offers two real-time feeds, both wrapped by SDK streamer classes (verified):

- **`MarketDataStreamerV3`** — live ticks (LTP, OHLC, depth, OI, greeks)
- **`PortfolioDataStreamer`** — order/position/holding updates

Both expose `.on(event, handler)`, `.connect()`, and `.auto_reconnect(...)`.
Events: `open`, `message`, `close`, `error`, `reconnecting`.

```python
import os, upstox_client

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
client = upstox_client.ApiClient(configuration)
```

---

## Market feed — `MarketDataStreamerV3`

Constructor: `MarketDataStreamerV3(api_client, instrumentKeys=[...], mode="full")`.

| Mode | Data |
|------|------|
| `ltpc` | LTP, last-traded qty, close, volume |
| `full` | LTP + OHLC + market depth + OI |
| `option_greeks` | IV, delta, gamma, theta, vega |

```python
streamer = upstox_client.MarketDataStreamerV3(
    client,
    instrumentKeys=["NSE_INDEX|Nifty 50", "NSE_EQ|INE002A01018"],
    mode="full",
)
streamer.auto_reconnect(True, 5, 10)        # enabled, interval=5s, retries=10

streamer.on("open",         lambda: print("connected"))
streamer.on("message",      lambda data: print("tick:", data))
streamer.on("error",        lambda err: print("error:", err))
streamer.on("close",        lambda *a: print("closed:", a))
streamer.on("reconnecting", lambda info: print("reconnecting:", info))

streamer.connect()                          # blocking; runs the event loop
```

Add/remove instruments after connecting:

```python
streamer.subscribe(["NSE_EQ|INE040A01034"], "ltpc")
streamer.unsubscribe(["NSE_EQ|INE040A01034"])
```

---

## Portfolio / order-update feed — `PortfolioDataStreamer`

```python
portfolio_feed = upstox_client.PortfolioDataStreamer(client)
portfolio_feed.on("open",    lambda: print("portfolio feed connected"))
portfolio_feed.on("message", lambda msg: print("update:", msg))
portfolio_feed.connect()
```

Delivers order placed/modified/cancelled/executed events, GTT triggers, and
position/holding changes.

---

## Authorization endpoints — `WebsocketApi`

If you build your own WebSocket client instead of the streamers, fetch the
authorized redirect URI first:

```python
ws = upstox_client.WebsocketApi(client)

market_auth = ws.get_market_data_feed_authorize("2.0")
print(market_auth.data.authorized_redirect_uri)

pf_auth = ws.get_portfolio_stream_feed_authorize(
    "2.0", order_update=True, holding_update=True, position_update=True
)
print(pf_auth.data.authorized_redirect_uri)
```

---

## Webhook (postback) alternative

If you can't hold a persistent socket, register a webhook URL in the developer
portal; Upstox POSTs order-update payloads to it. See the
[webhook docs](https://upstox.com/developer/api-documentation/).
