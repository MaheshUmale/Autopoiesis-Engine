# Kill Switch Reference

A **kill switch** lets a user temporarily halt all trading in a specific exchange
segment — a circuit breaker against emotional, compulsive, or runaway algorithmic
trading. When enabled for a segment, Upstox **cancels all pending orders** in that
segment and **blocks new orders** until it is turned off.

Exposed via `UserApi` (v2): `get_kill_switch()` and `update_kill_switch(body)`.

```python
import os, upstox_client

configuration = upstox_client.Configuration()
configuration.access_token = os.environ["UPSTOX_ACCESS_TOKEN"]
user_api = upstox_client.UserApi(upstox_client.ApiClient(configuration))
```

---

## Segments

`NSE_EQ`, `BSE_EQ`, `NSE_FO`, `BSE_FO`, `NCD_FO`, `BCD_FO`, `MCX_FO`, `NSE_COM`

## Enable / disable a segment — `update_kill_switch(body)`

`body` is a **list** of `{segment, action}` objects. `action` is `DISABLE`
(turn trading OFF — i.e. activate the kill switch) or `ENABLE` (turn trading
back ON). Multiple segments can be updated atomically in one call.

```python
# Activate the kill switch on NSE equity (halt trading)
body = [{"segment": "NSE_EQ", "action": "DISABLE"}]
resp = user_api.update_kill_switch(body)
print(resp)

# Lift it later (resume trading)
user_api.update_kill_switch([{"segment": "NSE_EQ", "action": "ENABLE"}])
```

## Check current state — `get_kill_switch()`

```python
status = user_api.get_kill_switch()
print(status)
```

---

## Important constraints

- **Close positions first** — a segment can only be disabled when it has no open positions.
- **Pending orders auto-cancel** — disabling a segment cancels its working orders.
- **12-hour cooling period** — once disabled, a segment cannot be re-enabled for ~12 hours. Warn the user that this is not instantly reversible before calling `DISABLE`.
- **All-or-nothing** — each request applies atomically; one bad segment fails the whole call.

> Treat `DISABLE` as a deliberate, hard-to-undo action. Always confirm the
> segment(s) with the user and surface the 12-hour lock-in before calling.
