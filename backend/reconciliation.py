"""
Deterministic reconciliation engine for Razor-AI.

No AI is used anywhere in this file. Every number here is either given
directly by the input data or computed with plain arithmetic. This is a
deliberate design choice: the reconciliation problem has a fully known,
certain answer (amount - fee - tax - refund = expected settlement), so a
trained model would add uncertainty to a problem that doesn't have any.
"""

import pandas as pd

TOLERANCE = 100          # paise (~Re 1) — absorbs rounding noise, not a real mismatch
MAX_SETTLEMENT_DAYS = 7  # beyond this, flag as a timing exception


def reconcile(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes the raw transaction batch and returns it with two new columns:
    - reconciliation_status: "matched" or "exception"
    - mismatch_type: None if matched, otherwise the classified cause
    - delta: settlement_amount - expected_settlement (None if not computable)
    """
    results = []
    seen_payment_ids = set()

    for _, row in df.iterrows():
        payment_id = row["payment_id"]

        # 1. Duplicate check — same payment_id appearing more than once
        if payment_id in seen_payment_ids:
            results.append({**row, "reconciliation_status": "exception",
                             "mismatch_type": "duplicate_record", "delta": None})
            continue
        seen_payment_ids.add(payment_id)

        # 2. Missing settlement check
        if pd.isna(row["settlement_id"]) or pd.isna(row["settlement_amount"]):
            results.append({**row, "reconciliation_status": "exception",
                             "mismatch_type": "missing_settlement", "delta": None})
            continue

        # 3. Core arithmetic check
        expected_settlement = row["amount"] - row["fee"] - row["tax"] - row["refund_amount"]
        delta = row["settlement_amount"] - expected_settlement

        # 4. Timing check
        days_to_settle = (row["settled_at"] - row["created_at"]).days
        if days_to_settle > MAX_SETTLEMENT_DAYS:
            results.append({**row, "reconciliation_status": "exception",
                             "mismatch_type": "timing_mismatch", "delta": delta})
            continue

        # 5. Independent fee-correctness check.
        # A wrong fee can still be internally consistent with the settlement
        # amount (if the settlement was computed off that same wrong fee), so
        # the delta check above alone cannot catch this. Fee correctness has
        # to be verified against the expected rate directly, not inferred
        # from whether the settlement arithmetic happens to balance.
        expected_fee = round(row["amount"] * 0.02)
        if abs(row["fee"] - expected_fee) > TOLERANCE:
            results.append({**row, "reconciliation_status": "exception",
                             "mismatch_type": "fee_miscalculation", "delta": delta})
            continue

        # 6. Within tolerance -> matched. Otherwise classify the likely cause.
        if abs(delta) <= TOLERANCE:
            results.append({**row, "reconciliation_status": "matched",
                             "mismatch_type": None, "delta": delta})
        else:
            mismatch_type = "unaccounted_refund" if row["refund_amount"] > 0 else "unclassified_discrepancy"
            results.append({**row, "reconciliation_status": "exception",
                             "mismatch_type": mismatch_type, "delta": delta})

    return pd.DataFrame(results)


def compute_metrics(reconciled: pd.DataFrame) -> dict:
    """Summary stats for the dashboard."""
    total = len(reconciled)
    matched = int((reconciled["reconciliation_status"] == "matched").sum())
    amount_reconciled = int(
        reconciled.loc[reconciled["reconciliation_status"] == "matched", "amount"].sum()
    )
    return {
        "total_records": total,
        "match_rate": round(matched / total, 4) if total else 0,
        "matched": matched,
        "exceptions": total - matched,
        "amount_reconciled": amount_reconciled,
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
    false_negatives = seeded_ids - flagged_ids          # missed a real mismatch
    false_positives = flagged_ids - seeded_ids           # flagged something that was actually fine

    detection_rate = round(len(true_positives) / len(seeded_ids), 4) if seeded_ids else 0

    return {
        "seeded_mismatches": len(seeded_ids),
        "correctly_detected": len(true_positives),
        "missed": len(false_negatives),
        "false_positives": len(false_positives),
        "detection_rate": detection_rate,
    }
