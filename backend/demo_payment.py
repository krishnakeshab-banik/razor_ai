"""
Builds ONE transaction record on demand, for the live "pay in the demo
ecommerce app, watch it appear in the dashboard" flow.

Deliberately reuses the exact same mismatch logic as data/generate_data.py
rather than inventing a second, separate way to construct a bad record --
the whole point of the demo is that a live payment behaves exactly like a
batch-seeded one, since it goes through the identical reconciliation engine.

Valid outcomes match the mismatch_type vocabulary used everywhere else in
the project: clean, missing_settlement, unaccounted_refund,
fee_miscalculation, timing_mismatch, duplicate_record.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from config import FEE_PCT, TAX_PCT

VALID_OUTCOMES = {
    "clean", "missing_settlement", "unaccounted_refund",
    "fee_miscalculation", "tax_line_mismatch", "timing_mismatch", "duplicate_record",
}


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def apply_outcome_fields(
    *,
    amount: int,
    payment_id: str,
    order_id: str,
    created_at,
    payment_method: str = "upi",
    status: str = "captured",
    outcome: str = "clean",
    gstin: str = "29AABCU9603R1ZX",
    source: str = "demo_store",
) -> list[dict]:
    """
    Overlay fee / tax / settlement mutations for a planted outcome.

    Real Razorpay Test Mode payments often have fee=0 and no settlement yet.
    Using the same expected 2% / 18% / T+2 ledger as synthetic rows means
    "clean" still matches, and the judge outcome picker still plants the
    intended break on a real payment_id.
    """
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"Unknown outcome '{outcome}'. Must be one of {sorted(VALID_OUTCOMES)}")

    fee = round(amount * FEE_PCT)
    tax = round(fee * TAX_PCT)
    refund_amount = 0
    row_status = status
    settlement_id = make_id("setl")
    settled_at = created_at + timedelta(days=2)
    settlement_amount = amount - fee - tax - refund_amount

    if outcome == "missing_settlement":
        settlement_id, settlement_amount = None, None

    elif outcome == "unaccounted_refund":
        refund_amount = round(amount * 0.25)
        row_status = "partially_refunded"
        settlement_amount = amount - fee - tax

    elif outcome == "fee_miscalculation":
        fee = round(fee * 0.5)
        settlement_amount = amount - fee - tax

    elif outcome == "timing_mismatch":
        settled_at = created_at + timedelta(days=10)

    elif outcome == "tax_line_mismatch":
        tax = round(fee * 0.42)
        settlement_amount = amount - fee - tax - refund_amount

    row = {
        "payment_id": payment_id, "order_id": order_id, "amount": amount,
        "fee": fee, "tax": tax, "refund_amount": refund_amount,
        "settlement_id": settlement_id, "settlement_amount": settlement_amount,
        "status": row_status, "created_at": created_at, "settled_at": settled_at,
        "payment_method": payment_method, "gstin": gstin, "source": source,
    }

    if outcome == "duplicate_record":
        return [dict(row), dict(row)]

    return [row]


def build_demo_transaction(amount_rupees: float, outcome: str = "clean") -> list[dict]:
    """
    Returns a list of one or two row dicts (two only for duplicate_record,
    which by definition needs the same payment_id to appear twice).

    amount_rupees: the amount entered on the demo checkout page, in rupees.
    outcome: one of VALID_OUTCOMES. Raises ValueError on anything else --
    fail loudly here rather than silently falling back to "clean", since a
    typo in the outcome should be caught immediately, not hidden.
    """
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"Unknown outcome '{outcome}'. Must be one of {sorted(VALID_OUTCOMES)}")

    amount = round(amount_rupees * 100)
    now = datetime.now()
    return apply_outcome_fields(
        amount=amount,
        payment_id=make_id("pay"),
        order_id=make_id("order"),
        created_at=now,
        outcome=outcome,
    )


def map_razorpay_payment(payment: dict, outcome: str = "clean") -> list[dict]:
    """
    Map a Razorpay Payments API payload onto the live-batch transaction schema.
    Keeps the real payment_id, order_id, amount, created_at, and method.
    """
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"Unknown outcome '{outcome}'. Must be one of {sorted(VALID_OUTCOMES)}")

    payment_id = str(payment.get("id") or "").strip()
    if not payment_id:
        raise ValueError("Razorpay payment is missing id")

    amount = int(payment.get("amount") or 0)
    if amount <= 0:
        raise ValueError("Razorpay payment amount must be positive")

    order_id = str(payment.get("order_id") or "").strip() or make_id("order")
    created_raw = payment.get("created_at")
    if isinstance(created_raw, (int, float)):
        created_at = datetime.fromtimestamp(int(created_raw))
    else:
        created_at = datetime.now()

    method = str(payment.get("method") or "upi").lower()
    status = str(payment.get("status") or "captured")
    if status == "authorized":
        status = "captured"

    return apply_outcome_fields(
        amount=amount,
        payment_id=payment_id,
        order_id=order_id,
        created_at=created_at,
        payment_method=method,
        status=status,
        outcome=outcome,
    )


def apply_refund(transactions, payment_id: str, amount_rupees: float | None = None):
    """
    Apply a customer refund to the live batch.

    Remaining refundable = captured amount − already refunded.
    If a settlement amount exists, it is recomputed as amount − fee − tax − refund
    so cash and GST follow the same ledger as reconciliation.
    Missing settlements stay missing.
    """
    import pandas as pd

    if transactions is None or getattr(transactions, "empty", True):
        raise ValueError("No payments are loaded to refund")

    df = transactions.copy()
    mask = df["payment_id"].astype(str) == str(payment_id)
    if not mask.any():
        raise ValueError(f"Payment {payment_id} is not in the current batch")

    idx = df.index[mask][0]
    amount = float(df.at[idx, "amount"] or 0)
    already = float(df.at[idx, "refund_amount"] or 0) if "refund_amount" in df.columns else 0.0
    remaining = max(0.0, amount - already)
    if remaining <= 0:
        raise ValueError("This payment is already fully refunded")

    requested = remaining if amount_rupees is None else round(float(amount_rupees) * 100)
    if requested <= 0:
        raise ValueError("amount_rupees must be positive")
    applied = min(requested, remaining)
    new_refund = already + applied
    status = "refunded" if new_refund >= amount - 0.5 else "partially_refunded"

    df.loc[mask, "refund_amount"] = new_refund
    if "status" in df.columns:
        df.loc[mask, "status"] = status

    for row_idx in df.index[mask]:
        settlement = df.at[row_idx, "settlement_amount"] if "settlement_amount" in df.columns else None
        try:
            missing = settlement is None or (isinstance(settlement, float) and pd.isna(settlement))
        except (TypeError, ValueError):
            missing = settlement is None
        if missing:
            continue
        fee = float(df.at[row_idx, "fee"] or 0) if "fee" in df.columns else 0.0
        tax = float(df.at[row_idx, "tax"] or 0) if "tax" in df.columns else 0.0
        df.at[row_idx, "settlement_amount"] = amount - fee - tax - new_refund

    order_id = df.at[idx, "order_id"] if "order_id" in df.columns else None
    return df, {
        "payment_id": str(payment_id),
        "order_id": None if order_id is None or (isinstance(order_id, float) and pd.isna(order_id)) else str(order_id),
        "applied_paise": int(applied),
        "applied_rupees": round(applied / 100, 2),
        "refund_amount_paise": int(new_refund),
        "remaining_paise": int(max(0.0, amount - new_refund)),
        "status": status,
        "fully_refunded": status == "refunded",
    }
