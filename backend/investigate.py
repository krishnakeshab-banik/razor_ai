"""
Deterministic exception investigation and "explain this difference" waterfall.

No LLM. Every rupee in the waterfall is taken from the loaded row or from
config (expected fee / GST). If the remaining difference is not zero, the
function says so instead of inventing a bank credit.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from config import (
    AUTO_RESOLVE_CONFIDENCE,
    EXPECTED_SETTLEMENT_DAYS,
    FEE_PCT,
    MAX_SETTLEMENT_DAYS,
    REVIEW_CONFIDENCE,
    TAX_PCT,
    TOLERANCE_PAISE,
)
from explainations import explain
from resolution import suggest
from serialize import json_safe, paise_to_rupees


def _num(row: dict, key: str) -> float:
    value = row.get(key)
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 0.0
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _present(row: dict, key: str) -> bool:
    value = row.get(key)
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return False
    except (TypeError, ValueError):
        return bool(value)
    if isinstance(value, str) and not value.strip():
        return False
    return True


def related_records(reconciled: pd.DataFrame, payment_id: str) -> dict:
    matches = reconciled[reconciled["payment_id"] == payment_id]
    if matches.empty:
        return {"payment": None, "siblings": [], "same_order": [], "same_settlement": [], "same_utr": []}

    row = matches.iloc[-1].to_dict()
    order_id = row.get("order_id")
    settlement_id = row.get("settlement_id")
    utr = row.get("utr") if _present(row, "utr") else settlement_id

    same_order = reconciled[reconciled["order_id"] == order_id] if order_id is not None else reconciled.iloc[0:0]
    same_settlement = (
        reconciled[reconciled["settlement_id"] == settlement_id]
        if _present(row, "settlement_id")
        else reconciled.iloc[0:0]
    )
    same_utr = reconciled[reconciled["utr"] == utr] if _present(row, "utr") else reconciled.iloc[0:0]

    def slim(frame: pd.DataFrame) -> list:
        cols = [col for col in ["payment_id", "order_id", "amount", "settlement_id", "utr", "reconciliation_status", "mismatch_type"] if col in frame.columns]
        return [{key: json_safe(value) for key, value in rec.items()} for rec in frame[cols].to_dict(orient="records")]

    return {
        "payment": {key: json_safe(value) for key, value in row.items() if key != "processing_time_seconds"},
        "siblings": slim(matches),
        "same_order": slim(same_order),
        "same_settlement": slim(same_settlement),
        "same_utr": slim(same_utr),
    }


def explain_difference(row: dict) -> dict:
    amount = _num(row, "amount")
    fee = _num(row, "fee")
    tax = _num(row, "tax")
    refund = _num(row, "refund_amount")
    adjustment = _num(row, "adjustment")
    actual = row.get("settlement_amount")
    actual_num = _num(row, "settlement_amount") if _present(row, "settlement_amount") else None

    expected_fee = round(amount * FEE_PCT)
    expected_tax = round(expected_fee * TAX_PCT)
    # Same formula as reconcile(): adjustments are shown, not treated as known deductions.
    expected_net = amount - fee - tax - refund
    remaining = None if actual_num is None else actual_num - expected_net

    steps = [
        {"id": "gross", "label": "Expected / captured GMV", "paise": amount, "rupees": paise_to_rupees(amount)},
        {"id": "fee", "label": "Processing fee", "paise": -fee, "rupees": paise_to_rupees(-fee), "expected_paise": -expected_fee},
        {"id": "tax", "label": f"GST ({TAX_PCT:.0%} of fee)", "paise": -tax, "rupees": paise_to_rupees(-tax), "expected_paise": -expected_tax},
        {"id": "refund", "label": "Refunds", "paise": -refund, "rupees": paise_to_rupees(-refund)},
        {"id": "adjustment", "label": "Adjustments", "paise": -adjustment, "rupees": paise_to_rupees(-adjustment)},
        {"id": "expected_net", "label": "Expected net settlement", "paise": expected_net, "rupees": paise_to_rupees(expected_net)},
        {
            "id": "actual",
            "label": "Actual received / credited",
            "paise": actual_num,
            "rupees": None if actual_num is None else paise_to_rupees(actual_num),
            "missing": actual_num is None,
        },
        {
            "id": "remaining",
            "label": "Remaining unexplained difference",
            "paise": remaining,
            "rupees": None if remaining is None else paise_to_rupees(remaining),
        },
    ]

    fully_explained = remaining is not None and abs(remaining) <= TOLERANCE_PAISE
    missing = not _present(row, "settlement_id") or actual_num is None
    mismatch = row.get("mismatch_type")
    if missing:
        status = "Missing settlement — the engine will not invent a UTR"
        fully_explained = False
    elif mismatch in {"unknown_adjustment", "partial_settlement", "unclassified_discrepancy"}:
        status = "Unexplained amount remains"
        fully_explained = False
    elif fully_explained:
        status = "Fully explained"
    else:
        status = "Unexplained amount remains"

    return {
        "payment_id": row.get("payment_id"),
        "currency": "INR",
        "expected_gross_rupees": paise_to_rupees(amount),
        "expected_fee_rupees": paise_to_rupees(expected_fee),
        "actual_fee_rupees": paise_to_rupees(fee),
        "expected_tax_rupees": paise_to_rupees(expected_tax),
        "actual_tax_rupees": paise_to_rupees(tax),
        "refund_rupees": paise_to_rupees(refund),
        "adjustment_rupees": paise_to_rupees(adjustment),
        "expected_net_rupees": paise_to_rupees(expected_net),
        "actual_net_rupees": None if actual_num is None else paise_to_rupees(actual_num),
        "remaining_rupees": None if remaining is None else paise_to_rupees(remaining),
        "fully_explained": fully_explained,
        "status": status,
        "steps": steps,
        "tolerance_rupees": paise_to_rupees(TOLERANCE_PAISE),
        "rules": {
            "fee_pct": FEE_PCT,
            "tax_pct": TAX_PCT,
            "tax_base": "fee",
            "expected_settlement_days": EXPECTED_SETTLEMENT_DAYS,
            "max_settlement_days": MAX_SETTLEMENT_DAYS,
        },
    }


def _causes(row: dict, waterfall: dict) -> list[dict]:
    causes = []
    mismatch = row.get("mismatch_type")
    fee_gap = abs(_num(row, "fee") - round(_num(row, "amount") * FEE_PCT))
    tax_gap = abs(_num(row, "tax") - round(round(_num(row, "amount") * FEE_PCT) * TAX_PCT))

    if mismatch == "missing_settlement" or waterfall["actual_net_rupees"] is None:
        causes.append({
            "cause": "missing_settlement",
            "likelihood": 0.99,
            "detail": "No settlement_id / credited amount is present. Do not invent a bank UTR.",
        })
    if fee_gap > TOLERANCE_PAISE:
        causes.append({
            "cause": "fee_miscalculation",
            "likelihood": 0.95,
            "detail": f"Fee differs from {FEE_PCT:.0%} of GMV by ₹{paise_to_rupees(fee_gap)}.",
        })
    if tax_gap > TOLERANCE_PAISE:
        causes.append({
            "cause": "tax_line_mismatch",
            "likelihood": 0.94,
            "detail": f"GST differs from {TAX_PCT:.0%} of fee by ₹{paise_to_rupees(tax_gap)}.",
        })
    if _num(row, "refund_amount") > 0 and mismatch in {"unaccounted_refund", "unclassified_discrepancy", None}:
        causes.append({
            "cause": "unaccounted_refund",
            "likelihood": 0.93,
            "detail": "A refund exists on the payment and may not have reduced the credited amount.",
        })
    if mismatch == "duplicate_record":
        causes.append({
            "cause": "duplicate_record",
            "likelihood": 0.97,
            "detail": "The same payment_id appears more than once in this batch.",
        })
    if mismatch == "timing_mismatch":
        causes.append({
            "cause": "timing_mismatch",
            "likelihood": 0.9,
            "detail": f"Amounts can still match; settlement landed after {MAX_SETTLEMENT_DAYS} days.",
        })
    if mismatch == "partial_settlement":
        causes.append({
            "cause": "partial_settlement",
            "likelihood": 0.9,
            "detail": "A credit exists but is smaller than expected net. Remaining credit was not invented.",
        })
    if mismatch == "unknown_adjustment" or _num(row, "adjustment") > TOLERANCE_PAISE:
        causes.append({
            "cause": "unknown_adjustment",
            "likelihood": 0.8,
            "detail": "An adjustment reduced the credit without a classified fee/tax/refund line.",
        })
    if not causes:
        causes.append({
            "cause": "unclassified_discrepancy",
            "likelihood": 0.4,
            "detail": "Unable to determine with available evidence. Human review required.",
        })
    causes.sort(key=lambda item: item["likelihood"], reverse=True)
    return causes


def investigate(reconciled: pd.DataFrame, payment_id: str, resolutions: dict | None = None) -> dict:
    related = related_records(reconciled, payment_id)
    if related["payment"] is None:
        return {
            "found": False,
            "payment_id": payment_id,
            "what_happened": "Unable to determine with available evidence.",
            "recommended_action": "Human review required.",
        }

    row = reconciled[reconciled["payment_id"] == payment_id].iloc[-1].to_dict()
    waterfall = explain_difference(row)
    causes = _causes(row, waterfall)
    likely = causes[0]
    suggestion = suggest(row.get("mismatch_type"))
    confidence = float(row.get("confidence") or likely["likelihood"])
    if waterfall["fully_explained"] and suggestion.get("auto_fixable"):
        confidence = max(confidence, 0.95)

    if confidence >= AUTO_RESOLVE_CONFIDENCE and suggestion.get("auto_fixable"):
        automation = "auto_resolve"
        recommended = suggestion.get("label")
    elif confidence >= REVIEW_CONFIDENCE:
        automation = "human_approval"
        recommended = "Recommend the suggested fix, but a human must approve."
    else:
        automation = "do_not_resolve"
        recommended = "Human review required. Do not auto-resolve."

    evidence_ids = [payment_id]
    if _present(row, "settlement_id"):
        evidence_ids.append(str(row.get("settlement_id")))
    if _present(row, "order_id"):
        evidence_ids.append(str(row.get("order_id")))
    if _present(row, "utr"):
        evidence_ids.append(str(row.get("utr")))

    resolution = (resolutions or {}).get(payment_id)
    steps = [
        {"id": "payment", "label": "Payment record checked", "ok": _present(row, "payment_id"), "record_id": payment_id},
        {"id": "settlement", "label": "Settlement checked", "ok": _present(row, "settlement_id"), "record_id": json_safe(row.get("settlement_id"))},
        {"id": "bank", "label": "Bank transaction checked", "ok": _present(row, "utr") or _present(row, "settlement_id"), "record_id": json_safe(row.get("utr") or row.get("settlement_id"))},
        {"id": "refund", "label": "Refund records checked", "ok": True, "record_id": payment_id, "detail": f"refund_amount={_num(row, 'refund_amount')}"},
        {"id": "fee", "label": "Fee records checked", "ok": True, "record_id": payment_id, "detail": f"fee={_num(row, 'fee')}"},
        {"id": "gst", "label": "GST records checked", "ok": True, "record_id": payment_id, "detail": f"tax={_num(row, 'tax')}"},
        {"id": "calculation", "label": "Deterministic calculation performed", "ok": True, "record_id": payment_id},
        {"id": "explained", "label": "Difference explained" if waterfall["fully_explained"] else "Unexplained amount remains", "ok": bool(waterfall["fully_explained"]), "record_id": payment_id},
    ]
    return {
        "found": True,
        "investigated_at": datetime.now(timezone.utc).isoformat(),
        "investigation_steps": steps,
        "payment_id": payment_id,
        "exception_id": f"exc_{payment_id}",
        "mismatch_type": row.get("mismatch_type"),
        "workflow_status": (resolution or {}).get("workflow_status") or ("Open" if row.get("reconciliation_status") == "exception" else "Resolved"),
        "what_happened": explain(row),
        "expected_value_rupees": waterfall["expected_net_rupees"],
        "actual_value_rupees": waterfall["actual_net_rupees"],
        "difference_rupees": waterfall["remaining_rupees"],
        "waterfall": waterfall,
        "possible_causes": causes,
        "most_likely_cause": likely,
        "confidence": round(confidence, 4),
        "automation": automation,
        "recommended_action": recommended,
        "suggested_action": suggestion,
        "evidence_ids": evidence_ids,
        "evidence": row.get("evidence") if isinstance(row.get("evidence"), list) else [],
        "related": related,
        "ai_note": (
            "This investigation is deterministic. Gemini is not used to calculate "
            "fee, GST, refund, or settlement amounts."
        ),
    }


def dump_investigation(payload: dict) -> str:
    return json.dumps(payload, default=str)
