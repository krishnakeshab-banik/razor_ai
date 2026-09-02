"""JSON-safe conversions for pandas / numpy values returned by the API."""

from datetime import date, datetime

import pandas as pd


def json_safe(value):
    """Turn pandas/numpy/NaN/timestamps into JSON-serializable Python values."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    return value


def paise_to_rupees(value) -> float:
    return round(float(value or 0) / 100, 2)


def format_inr_compact(rupees) -> str:
    value = float(rupees or 0)
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if magnitude >= 100000:
        return f"{sign}₹{magnitude / 100000:.1f}L"
    return f"{sign}₹{magnitude:,.2f}"
