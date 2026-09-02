"""
Tests /demo/simulate-payment for every valid outcome, checking each one
actually produces the reconciliation result it claims to. This is the
endpoint the demo ecommerce app calls, so a bug here would surface live in
front of judges -- worth testing thoroughly.

Run: python tests/test_demo_payment.py
(run from the razor-ai/ root directory; no batch needs to be pre-loaded --
this endpoint is tested standalone, matching how the ecommerce app would
use it without necessarily hitting /batch/load first)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        raise AssertionError(label)


def simulate(amount, outcome):
    r = client.post("/demo/simulate-payment", json={"amount_rupees": amount, "outcome": outcome})
    check(f"'{outcome}' request returns 200", r.status_code == 200)
    return r.json()


def run():
    print("=== POST /demo/reset (start from a clean slate, no batch loaded) ===")
    client.post("/demo/reset")

    print("\n=== Test: clean payment (should match, no exception) ===")
    result = simulate(1000, "clean")
    payment = result["this_payment"]
    print(f"    {payment}")
    check("clean payment status is 'matched'", payment["reconciliation_status"] == "matched")
    check("clean payment has no mismatch_type", payment["mismatch_type"] is None)

    print("\n=== Test: missing_settlement ===")
    result = simulate(1500, "missing_settlement")
    payment = result["this_payment"]
    print(f"    {payment}")
    check("flagged as exception", payment["reconciliation_status"] == "exception")
    check("mismatch_type is missing_settlement", payment["mismatch_type"] == "missing_settlement")
    check("has a real explanation, not empty", bool(payment["explanation"]))

    print("\n=== Test: unaccounted_refund ===")
    result = simulate(2000, "unaccounted_refund")
    payment = result["this_payment"]
    print(f"    {payment}")
    check("flagged as exception", payment["reconciliation_status"] == "exception")
    check("mismatch_type is unaccounted_refund", payment["mismatch_type"] == "unaccounted_refund")

    print("\n=== Test: fee_miscalculation ===")
    result = simulate(1200, "fee_miscalculation")
    payment = result["this_payment"]
    print(f"    {payment}")
    check("flagged as exception", payment["reconciliation_status"] == "exception")
    check("mismatch_type is fee_miscalculation", payment["mismatch_type"] == "fee_miscalculation")

    print("\n=== Test: timing_mismatch ===")
    result = simulate(900, "timing_mismatch")
    payment = result["this_payment"]
    print(f"    {payment}")
    check("flagged as exception", payment["reconciliation_status"] == "exception")
    check("mismatch_type is timing_mismatch", payment["mismatch_type"] == "timing_mismatch")

    print("\n=== Test: duplicate_record ===")
    result = simulate(800, "duplicate_record")
    payment = result["this_payment"]
    print(f"    {payment}")
    check("flagged as exception", payment["reconciliation_status"] == "exception")
    check("mismatch_type is duplicate_record", payment["mismatch_type"] == "duplicate_record")

    print("\n=== Test: tax_line_mismatch ===")
    result = simulate(1100, "tax_line_mismatch")
    payment = result["this_payment"]
    check("flagged as exception", payment["reconciliation_status"] == "exception")
    check("mismatch_type is tax_line_mismatch", payment["mismatch_type"] == "tax_line_mismatch")

    print("\n=== Test: batch_metrics reflects the growing batch ===")
    metrics = result["batch_metrics"]
    print(f"    {metrics}")
    # 1 clean + 1 missing_settlement + 1 unaccounted_refund + 1 fee_miscalculation
    # + 1 timing_mismatch + 2 duplicate_record rows + 1 tax_line_mismatch = 8
    check("total_records reflects all payments simulated so far", metrics["total_records"] == 8)

    print("\n=== Test: invalid outcome is rejected cleanly, not a 500 crash ===")
    r = client.post("/demo/simulate-payment", json={"amount_rupees": 500, "outcome": "not_a_real_outcome"})
    check("invalid outcome returns 400, not 500", r.status_code == 400)

    print("\n=== Test: invalid amount is rejected cleanly ===")
    r = client.post("/demo/simulate-payment", json={"amount_rupees": -50, "outcome": "clean"})
    check("negative amount returns 400", r.status_code == 400)

    print("\n=== Test: the simulated payment is visible in /reconcile/exceptions ===")
    r = client.get("/reconcile/exceptions")
    exceptions = r.json()
    exception_ids = [e["payment_id"] for e in exceptions]
    check("at least 5 exceptions present (all the bad outcomes simulated)", len(exceptions) >= 5)
    print(f"    {len(exceptions)} exceptions currently in the batch")

    print("\n=== Test: the simulated payment is visible in /audit-trail ===")
    r = client.get("/audit-trail")
    audit = r.json()
    check("audit trail includes ecommerce_demo source",
          any(a["source"] == "ecommerce_demo" for a in audit))
    demo_entries = [a for a in audit if a["source"] == "ecommerce_demo"]
    print(f"    {len(demo_entries)} demo payment entries logged")

    client.post("/demo/reset")
    print("\nAll demo payment tests passed.")


if __name__ == "__main__":
    run()
