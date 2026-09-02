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
    assert "processing_time_seconds" in metrics and metrics["processing_time_seconds"] > 0, "Throughput must come from a real reconcile() timer"
    assert metrics["records_per_second"] == round(metrics["total_records"] / metrics["processing_time_seconds"], 2)
    print(f"  Throughput is measured: {metrics['records_per_second']}/s over {metrics['processing_time_seconds']:.4f}s")

    from reconciliation import compute_priority
    bands = {
        "Critical": compute_priority({"mismatch_type": "missing_settlement", "amount": 250000, "delta": None}),
        "High": compute_priority({"mismatch_type": "missing_settlement", "amount": 50000, "delta": None}),
        "Medium": compute_priority({"mismatch_type": "fee_miscalculation", "amount": 100000, "delta": 8000}),
        "Low": compute_priority({"mismatch_type": "timing_mismatch", "amount": 80000, "delta": 0}),
    }
    for expected, actual in bands.items():
        assert actual == expected, f"priority {expected} produced {actual}"
    live_bands = set(reconciled.loc[reconciled["reconciliation_status"] == "exception", "priority"].dropna().astype(str))
    print(f"  Live exception priority bands: {sorted(live_bands)}")
    assert len(live_bands) >= 3, f"Priority banding looks uniform: {live_bands}"

    print(f"  False positives ({evaluation['false_positives']}): {evaluation.get('false_positive_ids')}")
    print(f"  Misses ({evaluation['missed']}): {evaluation.get('missed_ids')}")
    review_cols = [col for col in ("payment_id", "mismatch_type", "delta", "amount", "priority") if col in reconciled.columns]
    if evaluation["false_positives"]:
        fp_mask = reconciled["payment_id"].astype(str).isin(evaluation["false_positive_ids"])
        print("\n=== False-positive review (row by row) ===")
        print(reconciled.loc[fp_mask, review_cols].to_string(index=False))
    if evaluation["missed"]:
        miss_mask = reconciled["payment_id"].astype(str).isin(evaluation["missed_ids"])
        print("\n=== Missed seeded mismatches ===")
        print(reconciled.loc[miss_mask, review_cols].to_string(index=False))

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "data"))
    from generate_data import generate_batch
    print("\n=== Fresh-batch validation (3 seeds) ===")
    for seed in (7, 11, 19):
        fresh_df, fresh_key = generate_batch(num_records=100, seed=seed)
        fresh = reconcile(fresh_df)
        fresh_eval = evaluate_against_answer_key(fresh, fresh_key)
        print(f"  seed {seed}: detection={fresh_eval['detection_rate']} fp={fresh_eval['false_positives']} miss={fresh_eval['missed']}")
        assert fresh_eval["missed"] == 0, f"fresh seed {seed} missed {fresh_eval['missed_ids']}"
        assert fresh_eval["false_positives"] == 0, f"fresh seed {seed} false positives {fresh_eval['false_positive_ids']}"
    print("\nAll checks passed.")


if __name__ == "__main__":
    run()
