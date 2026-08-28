"""
Root-cause explanation generator for Razor-AI.

Deliberately NOT powered by an LLM. By the time a record reaches this file,
the reconciliation engine has already computed the exact cause of the
mismatch with certainty (a specific delta, a specific missing field, a
specific rule that was violated). Generating the explanation from a template
guarantees the sentence is always factually correct and never invents a
number — an LLM here would only add hallucination risk to a fact that is
already fully known.

The chatbot (a separate file, chatbot.py) is the only place in this project
that uses an LLM, precisely because that is the only place where the input
(an arbitrary merchant question) is genuinely open-ended.
"""

TEMPLATES = {
    "missing_settlement": (
        "Payment {payment_id} for Rs {amount_rupees} has no matching settlement "
        "record. A settlement was expected within 2 days of {created_at}."
    ),
    "unaccounted_refund": (
        "Settlement short by Rs {delta_rupees}: a refund of Rs {refund_rupees} "
        "was issued on this payment but was not reflected in the settlement amount."
    ),
    "fee_miscalculation": (
        "Fee charged (Rs {fee_rupees}) does not match the expected 2% fee "
        "(Rs {expected_fee_rupees}) for a payment of Rs {amount_rupees}."
    ),
    "duplicate_record": (
        "Payment {payment_id} appears more than once in this batch. Only one "
        "settlement was expected for this payment."
    ),
    "timing_mismatch": (
        "Settlement for payment {payment_id} took {days} days to arrive, "
        "outside the expected 2-7 day settlement window."
    ),
    "unclassified_discrepancy": (
        "Settlement amount differs from the expected amount by Rs {delta_rupees}. "
        "The specific cause could not be automatically classified and needs review."
    ),
}


def _to_rupees(paise) -> str:
    """Formats a paise value as a rupee string with 2 decimals. Handles None/NaN safely."""
    if paise is None:
        return "0.00"
    try:
        if paise != paise:  # NaN check without importing pandas/numpy here
            return "0.00"
    except TypeError:
        pass
    return f"{paise / 100:,.2f}"


def explain(row: dict) -> str:
    """
    Takes one reconciled row (a dict with the fields reconciliation.py produces)
    and returns a plain-language explanation string.
    Returns a safe fallback message if the mismatch_type is missing or unrecognised,
    rather than raising an error — this function must never crash the API.
    """
    mismatch_type = row.get("mismatch_type")

    if not mismatch_type:
        return "No discrepancy detected."

    template = TEMPLATES.get(mismatch_type)
    if template is None:
        return f"Unrecognised discrepancy type: {mismatch_type}. Needs manual review."

    amount = row.get("amount") or 0
    expected_fee_paise = round(amount * 0.02)

    days = "?"
    if row.get("settled_at") and row.get("created_at"):
        try:
            days = (row["settled_at"] - row["created_at"]).days
        except TypeError:
            days = "?"

    values = {
        "payment_id": row.get("payment_id", "unknown"),
        "amount_rupees": _to_rupees(amount),
        "delta_rupees": _to_rupees(abs(row.get("delta") or 0)),
        "refund_rupees": _to_rupees(row.get("refund_amount") or 0),
        "fee_rupees": _to_rupees(row.get("fee") or 0),
        "expected_fee_rupees": _to_rupees(expected_fee_paise),
        "created_at": row.get("created_at", "unknown date"),
        "days": days,
    }

    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return f"Discrepancy of type {mismatch_type} detected, but the explanation could not be formatted."
