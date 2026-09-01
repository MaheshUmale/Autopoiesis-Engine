"""
upstox_helpers.py — Shared client factory and response helpers.

Reads credentials from environment variables (preferred) or, if unset, from a
local config.json. Never hardcode tokens.

Environment variables:
    UPSTOX_ACCESS_TOKEN          live access token (one trading day)
    UPSTOX_SANDBOX_ACCESS_TOKEN  sandbox token (paper trading)
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import upstox_client


_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"


def _config() -> dict:
    """Load config.json if present; environment variables take precedence."""
    if _CONFIG_PATH.exists():
        try:
            return json.loads(_CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _resolve_token(sandbox: bool) -> str:
    env_key = "UPSTOX_SANDBOX_ACCESS_TOKEN" if sandbox else "UPSTOX_ACCESS_TOKEN"
    cfg_key = "sandbox_access_token" if sandbox else "access_token"
    token = os.environ.get(env_key) or _config().get(cfg_key)
    if not token or token.startswith("PASTE"):
        raise RuntimeError(
            f"No access token found. Set {env_key} (recommended) or fill "
            f"'{cfg_key}' in config.json. Get a token from the Upstox "
            f"developer portal: https://account.upstox.com/developer/apps."
        )
    return token


def get_client(sandbox: bool = False) -> upstox_client.ApiClient:
    """Return a configured ApiClient. Pass sandbox=True for paper trading."""
    configuration = upstox_client.Configuration(sandbox=sandbox)
    configuration.access_token = _resolve_token(sandbox)
    return upstox_client.ApiClient(configuration)


# Convenience API-class accessors -------------------------------------------------

def order_api_v3(client=None):
    return upstox_client.OrderApiV3(client or get_client())


def order_api(client=None):
    return upstox_client.OrderApi(client or get_client())


def portfolio_api(client=None):
    return upstox_client.PortfolioApi(client or get_client())


def market_quote_v3(client=None):
    return upstox_client.MarketQuoteV3Api(client or get_client())


def options_api(client=None):
    return upstox_client.OptionsApi(client or get_client())


def instruments_api(client=None):
    return upstox_client.InstrumentsApi(client or get_client())


def user_api(client=None):
    return upstox_client.UserApi(client or get_client())


def unwrap(response):
    """Return the .data payload of an SDK response, or the response itself."""
    return getattr(response, "data", response)


if __name__ == "__main__":
    # Smoke test: confirm a token resolves and the profile call works.
    from upstox_client.rest import ApiException

    try:
        profile = user_api().get_profile(api_version="2.0")
        print("Authenticated as:", unwrap(profile).user_name)
    except ApiException as e:
        print("API error:", e.body)
    except RuntimeError as e:
        print(e)
