# Errors Reference

Rate limits live in `SKILL.md`. Breaching any limit returns HTTP
`429 Too Many Requests` — batch order placement with `place_multi_order` and
back off before retrying.

## Common HTTP Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| `400` | Bad request / invalid params | Check request body, required fields |
| `401` | Unauthorized | Token expired or invalid — re-authenticate |
| `403` | Forbidden | API not enabled for your account, or IP not whitelisted |
| `404` | Resource not found | Wrong order_id, instrument key, etc. |
| `429` | Rate limit exceeded | Back off and retry with exponential delay |
| `500` | Upstox server error | Retry after brief wait |
| `503` | Service unavailable | Retry — may be market open/close spike |

---

## Common API Error Codes

| Error code | Description |
|------------|-------------|
| `UDAPI10000` | This request is not supported by Upstox API — thrown when the API call is not recognized or valid, possibly due to incorrect URL formatting or unexpected characters in the URL. |
| `UDAPI100016` | Invalid Credentials — thrown when one of the credentials passed to this API is invalid. |
| `UDAPI10005` | Too Many Requests Sent — thrown when you've exceeded the rate limits for the API. |
| `UDAPI100015` | API Version does not exist — thrown when the API version isn't part of the header attributes. |
| `UDAPI100050` | Invalid token used to access API — thrown when an invalid token is used to access the API. |
| `UDAPI100067` | The API you are trying to access is not permitted with an extended_token — thrown when trying to access an API that is not allowed with an extended_token. |
| `UDAPI100036` | Invalid Input — thrown when an invalid input is passed to the API. |
| `UDAPI100038` | Invalid input passed to the API — thrown when an invalid input is passed to the API. |
| `UDAPI100073` | Your `client_id` is inactive — thrown when the client_id is not active. Contact the support team for assistance. |
| `UDAPI100500` | Something went wrong... please contact us — an unexpected error occurred. Contact support. |

Error codes specific to each API are detailed in the 4XX response section within
their respective documentation.

---

## Handling Token Expiry

Access tokens expire at the end of each trading day. Detect and handle:

```python
def api_call_with_auth_retry(api_func, *args, **kwargs):
    try:
        return api_func(*args, **kwargs)
    except ApiException as e:
        if e.status == 401:
            print("Token expired. Please regenerate your access token.")
            raise SystemExit(1)
        raise
```

---

## Debug Mode

Enable verbose logging for troubleshooting:

```python
import upstox_client, logging

upstox_client.Configuration.debug = True
logging.basicConfig(level=logging.DEBUG)
```

---

## Upstox API Status

Check real-time API health: https://status.upstox.com
Community for issue reports: https://community.upstox.com/c/developer-api
