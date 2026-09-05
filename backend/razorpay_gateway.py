"""
Razorpay Test Mode helpers.

Credentials come from the environment only (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET).
This module never logs, prints, or returns the key secret.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _clean_key(value: str | None) -> str:
    return (value or "").strip().strip('"').strip("'").strip()


def credentials() -> tuple[str, str]:
    return _clean_key(os.environ.get("RAZORPAY_KEY_ID")), _clean_key(os.environ.get("RAZORPAY_KEY_SECRET"))


def is_configured() -> bool:
    key_id, key_secret = credentials()
    return bool(key_id and key_secret)


def public_key_id() -> str:
    return credentials()[0]


def client():
    import razorpay

    key_id, key_secret = credentials()
    if not key_id or not key_secret:
        raise RuntimeError("Razorpay test keys are not configured")
    return razorpay.Client(auth=(key_id, key_secret))


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Official Razorpay HMAC: hex(HMAC_SHA256(order_id|payment_id, key_secret))."""
    _, key_secret = credentials()
    if not key_secret or not order_id or not payment_id or not signature:
        return False
    expected = hmac.new(
        key_secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def create_order(amount_paise: int, notes: dict | None = None) -> dict:
    payload = {
        "amount": int(amount_paise),
        "currency": "INR",
        "receipt": f"nw_{uuid.uuid4().hex[:12]}",
        "payment_capture": 1,
    }
    if notes:
        payload["notes"] = {str(key): str(value) for key, value in notes.items() if value is not None}
    return client().order.create(payload)


def fetch_payment(payment_id: str) -> dict:
    return dict(client().payment.fetch(payment_id))


def fetch_order(order_id: str) -> dict:
    return dict(client().order.fetch(order_id))
