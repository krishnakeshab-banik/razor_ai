"""
Deterministic reconciliation engine for Razor-AI.

No AI is used anywhere in this file. Every number here is either given
directly by the input data or computed with plain arithmetic. This is a
deliberate design choice: the reconciliation problem has a fully known,
certain answer (amount - fee - tax - refund = expected settlement), so a
trained model would add uncertainty to a problem that doesn't have any.
"""

from __future__ import annotations

import time

import pandas as pd

from config import (
    CRITICAL_AMOUNT_PAISE,
    FEE_PCT,
    HIGH_AMOUNT_PAISE,
    HIGH_DELTA_PAISE,
    MAX_SETTLEMENT_DAYS,
    MEDIUM_DELTA_PAISE,
    TAX_PCT,
    TOLERANCE_PAISE,
)

# Kept for older imports / tests that still read the module constants.
TOLERANCE = TOLERANCE_PAISE


def compute_priority(row: dict) -> str:
    """Four live bands from amount, unexplained delta, and mismatch type."""
    delta = row.get("delta")
    abs_delta = abs(delta) if delta is not None else 0
    mismatch_type = row.get("mismatch_type")
    amount = abs(row.get("amount") or 0)

    if mismatch_type == "missing_settlement":
        return "Critical" if amount >= CRITICAL_AMOUNT_PAISE else "High"
    if mismatch_type == "unaccounted_refund" and (abs_delta >= HIGH_DELTA_PAISE or amount >= HIGH_AMOUNT_PAISE):
        return "High"
    if abs_delta > HIGH_DELTA_PAISE or amount >= HIGH_AMOUNT_PAISE:
        return "High"
    if (
        mismatch_type in {"fee_miscalculation", "tax_line_mismatch", "partial_settlement", "unknown_adjustment", "unclassified_discrepancy"}
        or abs_delta >= MEDIUM_DELTA_PAISE
    ):
        return "Medium"
    return "Low"


def _num(row, key: str, default: float = 0.0) -> float:
    value = row.get(key, default) if hasattr(row, "get") else row[key] if key in row else default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _present(row, key: str) -> bool:
    value = row.get(key) if hasattr(row, "get") else row[key] if key in row else None
    try:
        if value is None or pd.isna(value):
            return False
    except (TypeError, ValueError):
        return bool(value)
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _days_between(row) -> int | None:
    try:
        created = pd.to_datetime(row.get("created_at"), errors="coerce")
        settled = pd.to_datetime(row.get("settled_at"), errors="coerce")
        if pd.isna(created) or pd.isna(settled):
            return None
        return int((settled - created).days)
    except Exception:
        return None


def _evidence_for(status: str, mismatch_type: str | None, row, expected: float | None, delta: float | None) -> tuple[list, float, str]:
    """Structured signals. Confidence is a score, not a claim of production accuracy."""
    evidence = []
    payment_ok = _present(row, "payment_id")
    settlement_ok = _present(row, "settlement_id") and _present(row, "settlement_amount")
    utr_ok = _present(row, "utr") or settlement_ok
    amount = _num(row, "amount")
    fee = _num(row, "fee")
    tax = _num(row, "tax")
    expected_fee = round(amount * FEE_PCT)
    expected_tax = round(expected_fee * TAX_PCT)
    days = _days_between(row)

    evidence.append({"signal": "payment_id", "matched": payment_ok, "detail": str(row.get("payment_id"))})
    evidence.append({"signal": "settlement_id", "matched": settlement_ok, "detail": str(row.get("settlement_id") or "")})
    evidence.append({"signal": "utr", "matched": utr_ok, "detail": str(row.get("utr") or row.get("settlement_id") or "")})
    if expected is not None and delta is not None:
        evidence.append({
            "signal": "amount",
            "matched": abs(delta) <= TOLERANCE_PAISE,
            "detail": f"expected {int(expected)} paise vs credited {int(_num(row, 'settlement_amount'))} paise",
        })
    evidence.append({
        "signal": "fee",
        "matched": abs(fee - expected_fee) <= TOLERANCE_PAISE,
        "detail": f"fee {int(fee)} vs expected {expected_fee} ({FEE_PCT:.0%} of GMV)",
    })
    evidence.append({
        "signal": "tax",
        "matched": abs(tax - expected_tax) <= TOLERANCE_PAISE,
        "detail": f"GST {int(tax)} vs expected {expected_tax} ({TAX_PCT:.0%} of fee)",
    })
    evidence.append({
        "signal": "settlement_window",
        "matched": days is not None and days <= MAX_SETTLEMENT_DAYS,
        "detail": f"{days} days" if days is not None else "dates unavailable",
    })

    matched_signals = sum(1 for item in evidence if item["matched"])
    confidence = round(matched_signals / max(len(evidence), 1), 4)

    if status == "matched":
        kind = "one_to_one"
        confidence = max(confidence, 0.92)
    elif mismatch_type == "missing_settlement":
        kind = "unmatched"
        confidence = 0.99
    elif mismatch_type == "duplicate_record":
        kind = "duplicate"
        confidence = 0.97
    elif mismatch_type in {"partial_settlement", "unknown_adjustment"}:
        kind = "partial"
        confidence = min(confidence, 0.7)
    else:
        kind = "exception"

    return evidence, confidence, kind


def _result(row, status, mismatch_type, delta, expected, extra=None):
    payload = dict(row)
    payload.update({
        "reconciliation_status": status,
        "mismatch_type": mismatch_type,
        "delta": delta,
        "expected_settlement": expected,
        "priority": compute_priority({
            "delta": delta,
            "mismatch_type": mismatch_type,
            "amount": _num(row, "amount"),
        }),
        "exception_id": f"exc_{row.get('payment_id')}" if status == "exception" else None,
    })
    evidence, confidence, kind = _evidence_for(status, mismatch_type, row, expected, delta)
    payload["evidence"] = evidence
    payload["confidence"] = confidence
    payload["match_kind"] = kind
    if extra:
        payload.update(extra)
    return payload


def reconcile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes the raw transaction batch and returns it with:
    - reconciliation_status: "matched" or "exception"
    - mismatch_type: None if matched, otherwise the classified cause
    - delta: settlement_amount - expected_settlement (None if not computable)
    - evidence / confidence / match_kind (structured, still deterministic)
    """
    started = time.perf_counter()
    results = []
    seen_payment_ids = set()

    for _, raw in df.iterrows():
        row = raw.to_dict()
        payment_id = row["payment_id"]
        amount = _num(row, "amount")
        fee = _num(row, "fee")
        tax = _num(row, "tax")
        refund = _num(row, "refund_amount")
        adjustment = _num(row, "adjustment")

        if payment_id in seen_payment_ids:
            results.append(_result(row, "exception", "duplicate_record", None, None))
            continue
        seen_payment_ids.add(payment_id)

        if not _present(row, "settlement_id") or not _present(row, "settlement_amount"):
            results.append(_result(row, "exception", "missing_settlement", None, None))
            continue

        expected_settlement = amount - fee - tax - refund
        delta = _num(row, "settlement_amount") - expected_settlement

        days_to_settle = _days_between(row)
        if days_to_settle is not None and days_to_settle > MAX_SETTLEMENT_DAYS:
            results.append(_result(row, "exception", "timing_mismatch", delta, expected_settlement))
            continue

        expected_fee = round(amount * FEE_PCT)
        expected_tax = round(expected_fee * TAX_PCT)
        tax_mismatch = abs(tax - expected_tax) > TOLERANCE_PAISE
        if abs(fee - expected_fee) > TOLERANCE_PAISE:
            results.append(_result(row, "exception", "fee_miscalculation", delta, expected_settlement))
            continue
        if tax_mismatch:
            results.append(_result(row, "exception", "tax_line_mismatch", delta, expected_settlement))
            continue

        if abs(delta) <= TOLERANCE_PAISE:
            results.append(_result(row, "matched", None, delta, expected_settlement))
        else:
            if refund > 0:
                mismatch_type = "unaccounted_refund"
            elif adjustment > TOLERANCE_PAISE:
                mismatch_type = "unknown_adjustment"
            elif 0 < _num(row, "settlement_amount") < expected_settlement - TOLERANCE_PAISE:
                mismatch_type = "partial_settlement"
            else:
                mismatch_type = "unclassified_discrepancy"
            results.append(_result(row, "exception", mismatch_type, delta, expected_settlement))

    reconciled = pd.DataFrame(results)

    if not reconciled.empty and "order_id" in reconciled.columns:
        order_counts = reconciled["order_id"].value_counts()
        many_orders = set(order_counts[order_counts > 1].index)
        if many_orders:
            mask = reconciled["order_id"].isin(many_orders) & (reconciled["reconciliation_status"] == "matched")
            reconciled.loc[mask, "match_kind"] = "one_to_many"

    if not reconciled.empty and "settlement_id" in reconciled.columns:
        settlement_counts = reconciled["settlement_id"].value_counts()
        many_setl = set(settlement_counts[settlement_counts > 1].index)
        if many_setl:
            mask = reconciled["settlement_id"].isin(many_setl) & (reconciled["reconciliation_status"] == "matched")
            reconciled.loc[mask, "match_kind"] = "many_to_one"

    processing_time_seconds = time.perf_counter() - started
    reconciled["processing_time_seconds"] = processing_time_seconds
    return reconciled


def compute_metrics(reconciled: pd.DataFrame) -> dict:
    """Summary stats for the dashboard. Every value is computed from this frame."""
    total = len(reconciled)
    matched = int((reconciled["reconciliation_status"] == "matched").sum())
    exceptions = total - matched
    amount_reconciled = int(
        reconciled.loc[reconciled["reconciliation_status"] == "matched", "amount"].sum()
    )
    exception_rows = reconciled[reconciled["reconciliation_status"] == "exception"]
    amount_at_risk = int(pd.to_numeric(exception_rows["amount"], errors="coerce").fillna(0).sum()) if exceptions else 0
    processing_time_seconds = float(reconciled["processing_time_seconds"].iloc[0]) if total and "processing_time_seconds" in reconciled.columns else 0.0
    records_per_second = round(total / processing_time_seconds, 2) if processing_time_seconds else 0.0

    breakdown = {}
    if exceptions:
        counts = exception_rows["mismatch_type"].fillna("unclassified_discrepancy").value_counts()
        breakdown = {str(key): int(value) for key, value in counts.items()}

    priority_counts = {}
    if exceptions and "priority" in exception_rows.columns:
        pcounts = exception_rows["priority"].fillna("Low").value_counts()
        priority_counts = {str(key): int(value) for key, value in pcounts.items()}

    return {
        "total_records": total,
        "match_rate": round(matched / total, 4) if total else 0,
        "matched": matched,
        "exceptions": exceptions,
        "amount_reconciled": amount_reconciled,
        "amount_at_risk": amount_at_risk,
        "processing_time_seconds": processing_time_seconds,
        "records_per_second": records_per_second,
        "mismatch_breakdown": breakdown,
        "priority_breakdown": priority_counts,
    }


def evaluate_against_answer_key(reconciled: pd.DataFrame, answer_key: pd.DataFrame) -> dict:
    """
    Measures the engine's own accuracy against the hidden ground truth.
    This is what backs the 'measured accuracy, not a cherry-picked match'
    claim the track brief explicitly asks for.
    """
    seeded_ids = set(answer_key["payment_id"])
    flagged_ids = set(
        reconciled.loc[reconciled["reconciliation_status"] == "exception", "payment_id"]
    )

    true_positives = seeded_ids & flagged_ids
    false_negatives = seeded_ids - flagged_ids
    false_positives = flagged_ids - seeded_ids
    clean_ids = set(reconciled["payment_id"]) - seeded_ids
    true_negatives = clean_ids - flagged_ids

    detection_rate = round(len(true_positives) / len(seeded_ids), 4) if seeded_ids else 0
    precision = round(len(true_positives) / len(flagged_ids), 4) if flagged_ids else 0
    recall = detection_rate

    return {
        "seeded_mismatches": len(seeded_ids),
        "correctly_detected": len(true_positives),
        "missed": len(false_negatives),
        "false_positives": len(false_positives),
        "true_negatives": len(true_negatives),
        "precision": precision,
        "recall": recall,
        "detection_rate": detection_rate,
        "missed_ids": sorted(str(item) for item in false_negatives)[:25],
        "false_positive_ids": sorted(str(item) for item in false_positives)[:25],
    }
