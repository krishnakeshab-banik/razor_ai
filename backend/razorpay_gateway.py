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
    cleaned = (value or "").replace("\ufeff", "").replace("\u200b", "").replace("\r", "")
    cleaned = cleaned.strip().strip('"').strip("'").strip()
    if "=" in cleaned:
        name, _, rest = cleaned.partition("=")
        label = name.strip()
        if label.lower().startswith("export "):
            label = label[7:].strip()
        if label.upper() in {"RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"}:
            cleaned = rest.strip().strip('"').strip("'").strip()
    return cleaned


def credentials() -> tuple[str, str]:
    return _clean_key(os.environ.get("RAZORPAY_KEY_ID")), _clean_key(os.environ.get("RAZORPAY_KEY_SECRET"))


def is_configured() -> bool:
    key_id, key_secret = credentials()
    return bool(key_id and key_secret)


def public_key_id() -> str:
    return credentials()[0]


def key_mode() -> str:
    key_id = public_key_id()
    if key_id.startswith("rzp_test_"):
        return "test"
    if key_id.startswith("rzp_live_"):
        return "live"
    return "unknown" if key_id else "missing"


def describe_gateway_error(exc: BaseException) -> str:
    """Safe operator-facing reason. Never includes the secret."""
    mode = key_mode()
    key_id, key_secret = credentials()
    if key_secret.startswith("rzp_") and not key_id.startswith("rzp_"):
        return "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET look swapped on Render. Put rzp_test_… in KEY_ID and the secret in KEY_SECRET, then restart."
    if mode == "live":
        return "These Razorpay keys are Live Mode. Demo checkout needs a Test Mode pair (KEY_ID starts with rzp_test_)."
    if mode == "unknown":
        return "RAZORPAY_KEY_ID on Render is not a Razorpay key. Paste only the value that starts with rzp_test_, not KEY_ID=…, then restart the service."
    pieces = [str(exc)]
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], dict):
        err = args[0].get("error") or args[0]
        if isinstance(err, dict):
            pieces.append(str(err.get("description") or ""))
            pieces.append(str(err.get("code") or ""))
    blob = " ".join(pieces).lower()
    if any(token in blob for token in ("auth", "401", "unauthorized", "invalid key", "authentication failed")):
        return (
            "Razorpay rejected the key pair. KEY_ID and KEY_SECRET must be the same Test Mode pair "
            "(Dashboard → Account & Settings → API Keys → Test Mode). No quotes. Save, then restart this Render service."
        )
    if any(token in blob for token in ("timeout", "timed out", "connection", "connect", "name or service", "max retries")):
        return "Render could not reach api.razorpay.com. Wait for the free instance to wake and try Pay again."
    if "amount" in blob:
        return "Razorpay rejected the amount. Pay at least ₹1."
    description = ""
    if args and isinstance(args[0], dict):
        err = args[0].get("error") or args[0]
        if isinstance(err, dict):
            description = str(err.get("description") or "").strip()
    if description and "secret" not in description.lower() and "key" not in description.lower():
        return f"Razorpay could not create the order: {description}"
    return (
        "Razorpay could not create the order. On this Render service, confirm RAZORPAY_KEY_ID starts with rzp_test_ "
        "and matches RAZORPAY_KEY_SECRET, then Manual Deploy → Clear build cache & deploy."
    )


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
    mode = key_mode()
    if mode != "test":
        raise RuntimeError(f"Razorpay key mode is {mode}")
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
