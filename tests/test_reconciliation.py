"""
Validates the reconciliation engine against the hidden ground-truth answer key.
Run this after every change to reconciliation.py before touching anything else.

Run: python tests/test_reconciliation.py
(run from the razor-ai/ root directory)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from reconciliation import reconcile, compute_metrics, evaluate_against_answer_key

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_data():
    df = pd.read_csv(
        os.path.join(DATA_DIR, "synthetic_batch.csv"),
        parse_dates=["created_at", "settled_at"],
    )
    answer_key = pd.read_csv(os.path.join(DATA_DIR, "answer_key.csv"))
    return df, answer_key


def run():
    df, answer_key = load_data()
    reconciled = reconcile(df)

    metrics = compute_metrics(reconciled)
    evaluation = evaluate_against_answer_key(reconciled, answer_key)

    print("=== Reconciliation metrics ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    print("\n=== Accuracy vs. hidden answer key ===")
    for k, v in evaluation.items():
        print(f"  {k}: {v}")

    print("\n=== Exceptions found (first 10) ===")
    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"]
    print(exceptions[["payment_id", "mismatch_type", "delta"]].head(10).to_string(index=False))

    # Basic pass/fail assertions — fail loudly if something is broken
    assert metrics["total_records"] == len(df), "Row count mismatch after reconciliation"
    assert evaluation["detection_rate"] >= 0.9, (
        f"Detection rate too low: {evaluation['detection_rate']} "
        f"(missed {evaluation['missed']} of {evaluation['seeded_mismatches']} seeded mismatches)"
    )
    print("\nAll checks passed.")


if __name__ == "__main__":
    run()
