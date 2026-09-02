"""
Multi-source ledger view and GST tax-line matcher.

Razorpay ops still breaks when payments, settlements and the implied bank
credit are compared by eye. These helpers expose the three ledgers side by
side, plus a GST line (18% of fee) that finance teams currently tick off
in a spreadsheet.
"""

from __future__ import annotations

import pandas as pd

from serialize import json_safe, paise_to_rupees
from config import TAX_PCT, TOLERANCE_PAISE


def build_source_view(reconciled: pd.DataFrame) -> dict:
    if reconciled is None or reconciled.empty:
        return {
            "payments": {"count": 0, "gmv_rupees": 0.0},
            "settlements": {"count": 0, "credited_rupees": 0.0},
            "expected_bank": {"count": 0, "expected_rupees": 0.0},
            "three_way_matches": 0,
            "breaks": [],
        }

    df = reconciled.copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["settlement_amount"] = pd.to_numeric(df["settlement_amount"], errors="coerce")
    df["expected_settlement"] = pd.to_numeric(df.get("expected_settlement"), errors="coerce")
    df["fee"] = pd.to_numeric(df["fee"], errors="coerce").fillna(0)
    df["tax"] = pd.to_numeric(df["tax"], errors="coerce").fillna(0)
    df["refund_amount"] = pd.to_numeric(df["refund_amount"], errors="coerce").fillna(0)

    has_settlement = df["settlement_id"].notna() & df["settlement_amount"].notna()
    expected = df["expected_settlement"].fillna(
        df["amount"] - df["fee"] - df["tax"] - df["refund_amount"]
    )

    three_way = (
        (df["reconciliation_status"] == "matched")
        & has_settlement
        & expected.notna()
    )

    breaks = []
    exceptions = df[df["reconciliation_status"] == "exception"]
    for _, row in exceptions.iterrows():
        breaks.append({
            "payment_id": row["payment_id"],
            "mismatch_type": row["mismatch_type"],
            "payments_gmv_rupees": paise_to_rupees(row["amount"]),
            "settlement_rupees": paise_to_rupees(row["settlement_amount"]) if pd.notna(row["settlement_amount"]) else None,
            "expected_bank_rupees": paise_to_rupees(expected.loc[row.name]),
            "has_settlement": bool(pd.notna(row.get("settlement_id"))),
            "priority": row.get("priority", "Low"),
        })

    return {
        "payments": {
            "count": int(len(df)),
            "gmv_rupees": paise_to_rupees(df["amount"].sum()),
            "fees_rupees": paise_to_rupees(df["fee"].sum()),
            "refunds_rupees": paise_to_rupees(df["refund_amount"].sum()),
        },
        "settlements": {
            "count": int(has_settlement.sum()),
            "credited_rupees": paise_to_rupees(df.loc[has_settlement, "settlement_amount"].sum()),
            "missing": int((~has_settlement).sum()),
        },
        "expected_bank": {
            "count": int(expected.notna().sum()),
            "expected_rupees": paise_to_rupees(expected.fillna(0).sum()),
        },
        "three_way_matches": int(three_way.sum()),
        "breaks": breaks,
    }


def build_tax_lines(reconciled: pd.DataFrame, tolerance_paise: int | None = None) -> dict:
    if tolerance_paise is None:
        tolerance_paise = TOLERANCE_PAISE
    if reconciled is None or reconciled.empty:
        return {
            "expected_gst_rupees": 0.0,
            "actual_gst_rupees": 0.0,
            "delta_rupees": 0.0,
            "matched_lines": 0,
            "mismatched_lines": 0,
            "lines": [],
        }

    df = reconciled.copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["fee"] = pd.to_numeric(df["fee"], errors="coerce").fillna(0)
    df["tax"] = pd.to_numeric(df["tax"], errors="coerce").fillna(0)

    lines = []
    matched = 0
    mismatched = 0
    expected_total = 0.0
    actual_total = 0.0

    for _, row in df.iterrows():
        expected_tax = round(float(row["fee"]) * TAX_PCT)
        actual_tax = float(row["tax"])
        delta = actual_tax - expected_tax
        is_match = abs(delta) <= tolerance_paise
        if is_match:
            matched += 1
        else:
            mismatched += 1
        expected_total += expected_tax
        actual_total += actual_tax
        if not is_match or row.get("mismatch_type") == "tax_line_mismatch":
            lines.append({
                "payment_id": row["payment_id"],
                "fee_rupees": paise_to_rupees(row["fee"]),
                "expected_gst_rupees": paise_to_rupees(expected_tax),
                "actual_gst_rupees": paise_to_rupees(actual_tax),
                "delta_rupees": paise_to_rupees(delta),
                "status": "matched" if is_match else "mismatch",
                "gstin": json_safe(row.get("gstin")),
                "payment_method": json_safe(row.get("payment_method")),
            })

    return {
        "rate": f"{TAX_PCT:.0%} GST on Razorpay processing fee",
        "tax_pct": TAX_PCT,
        "tax_base": "fee",
        "taxable_amount_rupees": paise_to_rupees(df["fee"].sum()),
        "gst_collected_rupees": paise_to_rupees(actual_total),
        "unresolved_gst_exceptions": int(
            ((df["reconciliation_status"] == "exception") & (df["mismatch_type"] == "tax_line_mismatch")).sum()
        ),
        "expected_gst_rupees": paise_to_rupees(expected_total),
        "actual_gst_rupees": paise_to_rupees(actual_total),
        "delta_rupees": paise_to_rupees(actual_total - expected_total),
        "matched_lines": matched,
        "mismatched_lines": mismatched,
        "lines": lines,
    }
