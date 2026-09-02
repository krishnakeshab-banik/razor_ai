"""Recurring discrepancy detection across the current batch (and past batches if present)."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from serialize import paise_to_rupees


def detect_recurring(reconciled: pd.DataFrame, history: list[dict] | None = None) -> list[dict]:
    if reconciled is None or reconciled.empty:
        return []

    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"]
    if exceptions.empty:
        return []

    buckets = defaultdict(lambda: {"count": 0, "amount": 0.0, "methods": set(), "ids": []})
    for _, row in exceptions.iterrows():
        key = str(row.get("mismatch_type") or "unclassified_discrepancy")
        method = str(row.get("payment_method") or "unknown")
        bucket_key = f"{key}|{method}"
        buckets[bucket_key]["count"] += 1
        buckets[bucket_key]["amount"] += float(row.get("amount") or 0)
        buckets[bucket_key]["methods"].add(method)
        buckets[bucket_key]["ids"].append(row["payment_id"])
        buckets[bucket_key]["type"] = key

    for item in history or []:
        key = item.get("bucket")
        if key in buckets:
            buckets[key]["count"] += int(item.get("count") or 0)
            buckets[key]["amount"] += float(item.get("amount") or 0)

    findings = []
    for bucket_key, payload in buckets.items():
        if payload["count"] < 2:
            continue
        mismatch_type, method = bucket_key.split("|", 1)
        findings.append({
            "bucket": bucket_key,
            "mismatch_type": mismatch_type,
            "payment_method": method,
            "occurrences": payload["count"],
            "affected_rupees": paise_to_rupees(payload["amount"]),
            "sample_payment_ids": payload["ids"][:5],
            "message": (
                f"Recurring discrepancy detected: {mismatch_type.replace('_', ' ')} "
                f"on {method} has occurred {payload['count']} times and affected "
                f"₹{paise_to_rupees(payload['amount']):,.2f}."
            ),
        })
    findings.sort(key=lambda item: item["affected_rupees"], reverse=True)
    return findings
