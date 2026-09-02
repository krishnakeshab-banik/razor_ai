"""
Synthetic / demo withdrawal ledger.

This is not a Razorpay payout API. It records a withdrawal against matched,
already-settled cash, subtracts previously withdrawn amounts, and never
pretends a bank transfer occurred.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from config import FEE_PCT, TAX_PCT
from database import insert_withdrawal, list_withdrawals, sum_withdrawn_paise
from serialize import paise_to_rupees


def _as_of(value) -> datetime:
    if value is None or str(value).strip() == "":
        return datetime.now()
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError("as_of is not a valid date.")
    ts = parsed.to_pydatetime()
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.replace(tzinfo=None)
    return ts


def _matched_settled(reconciled: pd.DataFrame, as_of: datetime) -> pd.DataFrame:
    if reconciled is None or reconciled.empty:
        return pd.DataFrame()
    df = reconciled.copy()
    df["settled_at"] = pd.to_datetime(df["settled_at"], errors="coerce")
    df["settlement_amount"] = pd.to_numeric(df["settlement_amount"], errors="coerce").fillna(0)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["fee"] = pd.to_numeric(df["fee"], errors="coerce").fillna(0)
    df["tax"] = pd.to_numeric(df["tax"], errors="coerce").fillna(0)
    df["refund_amount"] = pd.to_numeric(df["refund_amount"], errors="coerce").fillna(0)
    cap = min(as_of, datetime.now())
    return df[
        (df["reconciliation_status"] == "matched")
        & df["settled_at"].notna()
        & (df["settled_at"] <= pd.Timestamp(cap))
    ]


def availability(reconciled: pd.DataFrame, as_of=None) -> dict:
    as_of_dt = _as_of(as_of)
    eligible = _matched_settled(reconciled, as_of_dt)
    earned_paise = int(eligible["settlement_amount"].sum()) if not eligible.empty else 0
    gmv_paise = int(eligible["amount"].sum()) if not eligible.empty else 0
    fee_paise = int(eligible["fee"].sum()) if not eligible.empty else 0
    tax_paise = int(eligible["tax"].sum()) if not eligible.empty else 0
    refund_paise = int(eligible["refund_amount"].sum()) if not eligible.empty else 0
    withdrawn_paise = sum_withdrawn_paise()
    # FIFO: prior withdrawals consume the oldest eligible net first.
    available_paise = max(0, earned_paise - withdrawn_paise)
    return {
        "as_of": as_of_dt.isoformat(),
        "environment": "synthetic",
        "currency": "INR",
        "note": "Demo/synthetic withdrawal. No bank transfer is sent. Previously withdrawn funds are excluded.",
        "total_earned_rupees": paise_to_rupees(earned_paise),
        "gmv_rupees": paise_to_rupees(gmv_paise),
        "fees_already_charged_rupees": paise_to_rupees(fee_paise),
        "tax_already_charged_rupees": paise_to_rupees(tax_paise),
        "refunds_rupees": paise_to_rupees(refund_paise),
        "already_withdrawn_rupees": paise_to_rupees(withdrawn_paise),
        "pending_rupees": paise_to_rupees(0),
        "hold_rupees": paise_to_rupees(0),
        "available_rupees": paise_to_rupees(available_paise),
        "available_paise": available_paise,
        "eligible_payments": int(len(eligible)),
        "payout_fee_pct": FEE_PCT,
        "payout_tax_pct": TAX_PCT,
        "tax_base": "payout_fee",
    }


def analyze(reconciled: pd.DataFrame, requested_rupees: float, as_of=None) -> dict:
    avail = availability(reconciled, as_of)
    try:
        requested = float(requested_rupees)
    except (TypeError, ValueError):
        requested = 0.0
    requested_paise = int(round(max(0.0, requested) * 100))
    available_paise = avail["available_paise"]
    fee_paise = int(round(requested_paise * FEE_PCT))
    tax_paise = int(round(fee_paise * TAX_PCT))
    refund_paise = 0
    adjustment_paise = 0
    net_paise = requested_paise - fee_paise - tax_paise - refund_paise - adjustment_paise
    errors = []
    if requested_paise <= 0:
        errors.append("Withdrawal amount must be greater than zero.")
    if requested_paise > available_paise:
        errors.append("Cannot withdraw more than the available balance for this date.")
    if available_paise <= 0:
        errors.append("No additional amount is available for withdrawal for this period.")
    if net_paise <= 0 and requested_paise > 0:
        errors.append("Deductions consume the entire amount. Increase the request or check fee rules.")

    remaining_paise = available_paise - requested_paise if requested_paise <= available_paise else available_paise
    return {
        **avail,
        "requested_rupees": paise_to_rupees(requested_paise),
        "fee_rupees": paise_to_rupees(fee_paise),
        "tax_rupees": paise_to_rupees(tax_paise),
        "refund_adjustment_rupees": paise_to_rupees(refund_paise),
        "other_adjustment_rupees": paise_to_rupees(adjustment_paise),
        "net_rupees": paise_to_rupees(max(0, net_paise)),
        "available_after_rupees": paise_to_rupees(max(0, remaining_paise)),
        "can_withdraw": not errors,
        "errors": errors,
        "requested_paise": requested_paise,
        "fee_paise": fee_paise,
        "tax_paise": tax_paise,
        "refund_paise": refund_paise,
        "adjustment_paise": adjustment_paise,
        "net_paise": max(0, net_paise),
        "steps": [
            {"id": "gross", "label": "Gross withdrawal", "rupees": paise_to_rupees(requested_paise)},
            {"id": "refunds", "label": "Refunds / holds on this request", "rupees": paise_to_rupees(-refund_paise)},
            {"id": "fees", "label": f"Payout fee ({FEE_PCT:.0%} of request)", "rupees": paise_to_rupees(-fee_paise)},
            {"id": "tax", "label": f"GST on payout fee ({TAX_PCT:.0%})", "rupees": paise_to_rupees(-tax_paise)},
            {"id": "other", "label": "Other adjustments", "rupees": paise_to_rupees(-adjustment_paise)},
            {"id": "net", "label": "Actual amount you will receive", "rupees": paise_to_rupees(max(0, net_paise))},
        ],
    }


def execute(reconciled: pd.DataFrame, requested_rupees: float, as_of=None) -> dict:
    preview = analyze(reconciled, requested_rupees, as_of)
    if not preview["can_withdraw"]:
        raise ValueError(preview["errors"][0])
    record = insert_withdrawal(
        as_of=preview["as_of"],
        requested_paise=preview["requested_paise"],
        fee_paise=preview["fee_paise"],
        tax_paise=preview["tax_paise"],
        refund_paise=preview["refund_paise"],
        adjustment_paise=preview["adjustment_paise"],
        net_paise=preview["net_paise"],
        status="completed",
        environment="synthetic",
    )
    after = availability(reconciled, as_of)
    return {
        "withdrawal": record,
        "availability": after,
        "analysis": analyze(reconciled, 0, as_of),
        "environment": "synthetic",
        "message": "Synthetic withdrawal recorded. No money was transferred to a bank.",
    }


def history(query: str = "", start=None, end=None, limit: int = 100) -> list[dict]:
    return list_withdrawals(query=query, start=start, end=end, limit=limit)


def last_withdrawal() -> dict | None:
    items = list_withdrawals(limit=1)
    return items[0] if items else None


def seed_demo_withdrawals() -> list[dict]:
    """Two historical synthetic payouts so Withdraw/Reports are not an empty ledger."""
    if list_withdrawals(limit=1):
        return []
    now = datetime.now(timezone.utc)
    seeded = []
    for created, requested_paise in (
        (now - timedelta(days=52), 2500000),
        (now - timedelta(days=19), 1850000),
    ):
        fee_paise = round(requested_paise * FEE_PCT)
        tax_paise = round(fee_paise * TAX_PCT)
        seeded.append(insert_withdrawal(
            as_of=created.date().isoformat(),
            requested_paise=requested_paise,
            fee_paise=fee_paise,
            tax_paise=tax_paise,
            refund_paise=0,
            adjustment_paise=0,
            net_paise=requested_paise - fee_paise - tax_paise,
            status="completed",
            environment="synthetic",
            created_at=created.isoformat(),
        ))
    return seeded
