"""
Validates the explanation generator against real exceptions produced by the
reconciliation engine -- not made-up examples. Every exception type that
actually occurs in the batch must produce a clean, formatted sentence with
no crashes and no leftover {placeholder} text.

Run: python tests/test_explanations.py
(run from the razor-ai/ root directory, after generate_data.py has been run)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from reconciliation import reconcile
from explainations import explain

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def run():
    df = pd.read_csv(
        os.path.join(DATA_DIR, "synthetic_batch.csv"),
        parse_dates=["created_at", "settled_at"],
    )
    reconciled = reconcile(df)
    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"]

    print(f"Generating explanations for {len(exceptions)} exceptions...\n")

    seen_types = set()
    problems = []

    for _, row in exceptions.iterrows():
        row_dict = row.to_dict()
        explanation = explain(row_dict)
        seen_types.add(row_dict["mismatch_type"])

        if "{" in explanation or "}" in explanation:
            problems.append(f"  UNFILLED PLACEHOLDER -- {row_dict['payment_id']}: {explanation}")
        if not explanation.strip():
            problems.append(f"  EMPTY EXPLANATION -- {row_dict['payment_id']}")

        print(f"[{row_dict['mismatch_type']}] {row_dict['payment_id']}")
        print(f"  -> {explanation}\n")

    print("=== Coverage check ===")
    print(f"Mismatch types seen in this batch: {sorted(seen_types)}")

    if problems:
        print("\n=== PROBLEMS FOUND ===")
        for p in problems:
            print(p)
        raise AssertionError(f"{len(problems)} explanation(s) failed formatting checks")

    print("\nAll explanations generated cleanly. No crashes, no unfilled placeholders.")


if __name__ == "__main__":
    run()
