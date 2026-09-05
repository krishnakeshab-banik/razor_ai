"""
Merchant-facing finance rules. Defaults match the Razorpay-shaped demo
(2% fee, 18% GST on fee, T+2 / 7-day window). Nothing here is computed by
an LLM. Override via environment variables for a different merchant.
"""

import os
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """India wall clock, tz-naive so pandas cash/recon compares stay valid."""
    return datetime.now(IST).replace(tzinfo=None)


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


FEE_PCT = _float("RAZOR_AI_FEE_PCT", 0.02)
TAX_PCT = _float("RAZOR_AI_TAX_PCT", 0.18)
TOLERANCE_PAISE = _int("RAZOR_AI_TOLERANCE_PAISE", 100)
MAX_SETTLEMENT_DAYS = _int("RAZOR_AI_MAX_SETTLEMENT_DAYS", 7)
EXPECTED_SETTLEMENT_DAYS = _int("RAZOR_AI_EXPECTED_SETTLEMENT_DAYS", 2)
CURRENCY = os.environ.get("RAZOR_AI_CURRENCY", "INR")

AUTO_RESOLVE_CONFIDENCE = _float("RAZOR_AI_AUTO_RESOLVE_CONFIDENCE", 0.90)
REVIEW_CONFIDENCE = _float("RAZOR_AI_REVIEW_CONFIDENCE", 0.60)

MAX_UPLOAD_BYTES = _int("RAZOR_AI_MAX_UPLOAD_BYTES", 8 * 1024 * 1024)
MAX_UPLOAD_ROWS = _int("RAZOR_AI_MAX_UPLOAD_ROWS", 1000)
ALLOWED_GENERATE_COUNTS = (50, 100, 250, 500, 1000)

CRITICAL_AMOUNT_PAISE = _int("RAZOR_AI_CRITICAL_AMOUNT_PAISE", 200000)
HIGH_AMOUNT_PAISE = _int("RAZOR_AI_HIGH_AMOUNT_PAISE", 500000)
HIGH_DELTA_PAISE = _int("RAZOR_AI_HIGH_DELTA_PAISE", 100000)
MEDIUM_DELTA_PAISE = _int("RAZOR_AI_MEDIUM_DELTA_PAISE", 5000)


def public_config() -> dict:
    import razorpay_gateway

    return {
        "fee_pct": FEE_PCT,
        "tax_pct": TAX_PCT,
        "tax_base": "fee",
        "tolerance_paise": TOLERANCE_PAISE,
        "max_settlement_days": MAX_SETTLEMENT_DAYS,
        "expected_settlement_days": EXPECTED_SETTLEMENT_DAYS,
        "currency": CURRENCY,
        "auto_resolve_confidence": AUTO_RESOLVE_CONFIDENCE,
        "review_confidence": REVIEW_CONFIDENCE,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "max_upload_rows": MAX_UPLOAD_ROWS,
        "critical_amount_paise": CRITICAL_AMOUNT_PAISE,
        "high_amount_paise": HIGH_AMOUNT_PAISE,
        "high_delta_paise": HIGH_DELTA_PAISE,
        "medium_delta_paise": MEDIUM_DELTA_PAISE,
        "razorpay_test_configured": razorpay_gateway.is_configured(),
        "razorpay_key_mode": razorpay_gateway.key_mode(),
        "notes": (
            "Fee is a percentage of GMV. GST is a percentage of the fee, not of GMV. "
            "Change RAZOR_AI_FEE_PCT / RAZOR_AI_TAX_PCT if a merchant is not on standard pricing."
        ),
    }
