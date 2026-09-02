"""
Exception resolution — this is what actually closes the finance-ops loop.

Detection alone is not a controller. After reconciliation flags a row, a
human (or this agent) must either:
- apply a deterministic correction (fee/tax/refund arithmetic),
- waive a known timing delay,
- drop a duplicate, or
- escalate what cannot be auto-fixed (honest exception list).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from config import EXPECTED_SETTLEMENT_DAYS, FEE_PCT, TAX_PCT

AUTO_FIXABLE = {
    "fee_miscalculation",
    "tax_line_mismatch",
    "unaccounted_refund",
    "duplicate_record",
    "timing_mismatch",
}

HONEST_REMAINDER = {
    "missing_settlement",
    "unclassified_discrepancy",
    "partial_settlement",
    "unknown_adjustment",
    "duplicate_settlement",
}

SUGGESTIONS = {
    "missing_settlement": {
        "action": "escalate",
        "auto_fixable": False,
        "label": "Chase the missing settlement with the bank / Razorpay",
        "detail": "No settlement_id exists. The engine will not invent a bank credit.",
    },
    "fee_miscalculation": {
        "action": "apply_fix",
        "auto_fixable": True,
        "label": "Correct fee to configured % of GMV and recompute net settlement",
        "detail": "Default Razorpay-shaped pricing: fee = 2% of amount, GST = 18% of fee. Override RAZOR_AI_FEE_PCT / RAZOR_AI_TAX_PCT.",
    },
    "tax_line_mismatch": {
        "action": "apply_fix",
        "auto_fixable": True,
        "label": "Recompute GST at 18% of the processing fee",
        "detail": "GST is levied on the Razorpay fee, not on GMV.",
    },
    "unaccounted_refund": {
        "action": "apply_fix",
        "auto_fixable": True,
        "label": "Net the refund out of the settlement amount",
        "detail": "Refunds must reduce the amount credited to the merchant.",
    },
    "duplicate_record": {
        "action": "apply_fix",
        "auto_fixable": True,
        "label": "Drop the duplicate payment_id and keep the first row",
        "detail": "Only one settlement is expected per payment_id.",
    },
    "timing_mismatch": {
        "action": "waive",
        "auto_fixable": True,
        "label": "Accept the delayed settlement and normalise settled_at to T+2",
        "detail": "Amounts match; only the settlement window was breached.",
    },
    "unclassified_discrepancy": {
        "action": "escalate",
        "auto_fixable": False,
        "label": "Escalate for manual ledger review",
        "detail": "The arithmetic delta could not be classified automatically.",
    },
    "partial_settlement": {
        "action": "escalate",
        "auto_fixable": False,
        "label": "Chase the remaining settlement credit",
        "detail": "A partial credit exists. The engine will not invent the unpaid remainder.",
    },
    "unknown_adjustment": {
        "action": "escalate",
        "auto_fixable": False,
        "label": "Ask ops what the adjustment line is",
        "detail": "An unexplained adjustment reduced the credit. Human review required.",
    },
    "duplicate_settlement": {
        "action": "escalate",
        "auto_fixable": False,
        "label": "Confirm whether two payments share one UTR",
        "detail": "The same settlement identifier appears on more than one payment.",
    },
}


def suggest(mismatch_type: str | None) -> dict:
    if not mismatch_type:
        return {
            "action": "none",
            "auto_fixable": False,
            "label": "No action required",
            "detail": "Record already matched.",
        }
    return SUGGESTIONS.get(mismatch_type, SUGGESTIONS["unclassified_discrepancy"])


def _recompute_settlement(row: pd.Series) -> pd.Series:
    amount = float(row.get("amount") or 0)
    fee = float(row.get("fee") or 0)
    tax = float(row.get("tax") or 0)
    refund = float(row.get("refund_amount") or 0)
    row["settlement_amount"] = amount - fee - tax - refund
    return row


def apply_fix(transactions: pd.DataFrame, payment_id: str, mismatch_type: str) -> pd.DataFrame:
    """Mutate the loaded batch so the next reconcile pass can match the row."""
    df = transactions.copy()
    mask = df["payment_id"] == payment_id
    if not mask.any():
        raise ValueError(f"Payment {payment_id} is not in the current batch")

    if mismatch_type == "duplicate_record":
        first_idx = df.index[mask][0]
        drop_idx = df.index[mask][1:]
        return df.drop(index=drop_idx).reset_index(drop=True) if len(drop_idx) else df

    idx = df.index[mask][0]
    row = df.loc[idx].copy()
    amount = float(row.get("amount") or 0)

    if mismatch_type == "fee_miscalculation":
        fee = round(amount * FEE_PCT)
        tax = round(fee * TAX_PCT)
        row["fee"] = fee
        row["tax"] = tax
        row = _recompute_settlement(row)

    elif mismatch_type == "tax_line_mismatch":
        fee = float(row.get("fee") or 0)
        row["tax"] = round(fee * TAX_PCT)
        row = _recompute_settlement(row)

    elif mismatch_type == "unaccounted_refund":
        row = _recompute_settlement(row)

    elif mismatch_type == "timing_mismatch":
        created = pd.to_datetime(row.get("created_at"), errors="coerce")
        if pd.notna(created):
            row["settled_at"] = created + pd.Timedelta(days=EXPECTED_SETTLEMENT_DAYS)

    else:
        raise ValueError(f"{mismatch_type} cannot be auto-fixed")

    df.loc[idx] = row
    return df


def auto_fixable_ids(reconciled: pd.DataFrame, resolutions: dict) -> list[str]:
    open_exceptions = reconciled[reconciled["reconciliation_status"] == "exception"]
    ids = []
    for _, row in open_exceptions.iterrows():
        payment_id = row["payment_id"]
        existing = resolutions.get(payment_id, {})
        if existing.get("status") in {"resolved", "escalated", "waived"}:
            continue
        if row["mismatch_type"] in AUTO_FIXABLE:
            ids.append(payment_id)
    return ids


WORKFLOW_BY_ACTION = {
    "apply_fix": ("resolved", "Resolved"),
    "waive": ("resolved", "Resolved"),
    "escalate": ("escalated", "Unresolved"),
    "acknowledge": ("acknowledged", "Investigating"),
    "investigate": ("investigating", "Investigating"),
    "assign": ("assigned", "Awaiting Review"),
    "approve": ("resolved", "Resolved"),
    "reject": ("rejected", "Rejected"),
    "add_note": ("noted", "Investigating"),
    "reopen": ("reopened", "Open"),
}


def stamp_resolution(payment_id: str, action: str, mismatch_type: str, note: str = "", actor: str = "finance_ops") -> dict:
    status, workflow = WORKFLOW_BY_ACTION.get(action, ("escalated", "Unresolved"))
    return {
        "payment_id": payment_id,
        "action": action,
        "mismatch_type": mismatch_type,
        "status": status,
        "workflow_status": workflow,
        "note": note,
        "actor": actor,
        "at": datetime.now(timezone.utc).isoformat(),
    }
