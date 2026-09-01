"""
validate_order.py — Pre-flight order validation with safety guardrails.

Run this BEFORE placing any live order. It builds a human-readable preview and
flags problems. It does not place anything itself.

Checks:
  1. instrument_token format (SEGMENT|IDENTIFIER)
  2. Known product code
  3. F&O lot-size multiple (pass lot_size, resolved via instrument_search)
  4. LIMIT orders require price > 0; MARKET orders get a caution
  5. Quantity > 0
"""

from __future__ import annotations

KNOWN_PRODUCTS = {"I", "D", "MTF"}
_FO_SEGMENTS = {"NSE_FO", "BSE_FO", "MCX_FO", "NCD_FO", "BCD_FO"}


def validate_order(instrument_token, transaction_type, order_type, product,
                   quantity, price, lot_size=None):
    """Return {'valid', 'errors', 'warnings', 'order_preview'}.

    lot_size — for F&O, the instrument's lot size (resolve it via
    instrument_search.resolve_instrument_key(...)['lot_size']). If omitted for an
    F&O token, the multiple check is skipped with a warning.
    """
    errors, warnings = [], []

    # 1. instrument_token format
    if "|" not in instrument_token:
        return _result(False, [f"Invalid instrument_token '{instrument_token}'. "
                               f"Use 'SEGMENT|IDENTIFIER' e.g. 'NSE_EQ|INE002A01018'."], [], {})
    segment, _ = instrument_token.split("|", 1)

    # 2. product
    if product not in KNOWN_PRODUCTS:
        errors.append(f"Unknown product '{product}'. Valid: {sorted(KNOWN_PRODUCTS)}.")

    # 3. F&O lot-size multiple
    if segment in _FO_SEGMENTS:
        if lot_size:
            lot = int(lot_size)
            if quantity % lot != 0:
                suggested = max(lot, round(quantity / lot) * lot)
                errors.append(f"Quantity {quantity} is not a multiple of lot size "
                              f"{lot}. Use {suggested}.")
        else:
            warnings.append("Lot-size check skipped: pass lot_size from "
                            "instrument_search to verify F&O quantity multiples.")

    # 4. price / order type
    if order_type == "LIMIT" and price <= 0:
        errors.append("LIMIT orders require price > 0.")
    if order_type == "MARKET":
        warnings.append("MARKET order: executes at the prevailing price. Prefer LIMIT for control.")

    # 5. quantity
    if quantity <= 0:
        errors.append("Quantity must be greater than 0.")

    notional = price * quantity if price > 0 else 0
    preview = {
        "instrument_token": instrument_token,
        "transaction_type": transaction_type,
        "order_type": order_type,
        "product": product,
        "quantity": quantity,
        "price": price,
        "estimated_notional": f"₹{notional:,.2f}" if notional else "market price",
    }
    return _result(not errors, errors, warnings, preview)


def _result(valid, errors, warnings, preview):
    return {"valid": valid, "errors": errors, "warnings": warnings, "order_preview": preview}


def print_validation_result(result):
    print("\n" + "=" * 52)
    print("ORDER PREVIEW")
    print("=" * 52)
    for k, v in result["order_preview"].items():
        print(f"  {k:<22}: {v}")
    for w in result["warnings"]:
        print(f"  [warn] {w}")
    for e in result["errors"]:
        print(f"  [ERROR] {e}")
    print("-" * 52)
    print("PASSED — confirm with the user before placing." if result["valid"]
          else "FAILED — fix errors before placing.")
    print("=" * 52 + "\n")


if __name__ == "__main__":
    print_validation_result(validate_order(
        instrument_token="NSE_EQ|INE002A01018",
        transaction_type="BUY", order_type="LIMIT", product="D",
        quantity=10, price=2500.0,
    ))
