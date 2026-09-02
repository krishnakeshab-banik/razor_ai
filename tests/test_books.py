"""
Tests the finance-ops loop: cash position, tax lines, multi-source ledgers,
exception resolution, and /books/close.

Run: python tests/test_books.py
"""

import os
import sys

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


def run():
    client.post("/demo/reset")

    print("=== Load + reconcile ===")
    r = client.post("/batch/load")
    check("load 200", r.status_code == 200)
    check("50+ records", r.json()["loaded"] >= 50)

    r = client.post("/reconcile/run")
    check("reconcile 200", r.status_code == 200)
    initial = r.json()
    check("match_rate present", "match_rate" in initial)
    check("mismatch_breakdown present", isinstance(initial.get("mismatch_breakdown"), dict))
    check("validation present", "validation" in initial)
    print(f"    initial match rate {initial['match_rate']*100:.1f}% / {initial['exceptions']} exceptions")

    print("\n=== Cash position ===")
    r = client.get("/cash/position")
    check("cash 200", r.status_code == 200)
    cash = r.json()
    check("7-day forecast", isinstance(cash.get("forecast"), list) and len(cash["forecast"]) == 7)
    check("available is numeric", isinstance(cash.get("available_rupees"), (int, float)))

    print("\n=== Multi-source ledgers ===")
    r = client.get("/ledgers/sources")
    check("sources 200", r.status_code == 200)
    sources = r.json()
    check("payments count matches batch", sources["payments"]["count"] == initial["total_records"])
    check("breaks list present", isinstance(sources.get("breaks"), list))

    print("\n=== Tax lines ===")
    r = client.get("/tax/lines")
    check("tax 200", r.status_code == 200)
    tax = r.json()
    check("matched + mismatched = total", tax["matched_lines"] + tax["mismatched_lines"] == initial["total_records"])

    print("\n=== Resolve one auto-fixable exception ===")
    exceptions = client.get("/reconcile/exceptions").json()
    fixable = next((item for item in exceptions if item["suggested_action"]["auto_fixable"]), None)
    if fixable:
        r = client.post("/exceptions/resolve", json={
            "payment_id": fixable["payment_id"],
            "action": "apply_fix",
        })
        check("resolve 200", r.status_code == 200)
        check("resolution stamped", r.json()["resolution"]["status"] in {"resolved", "waived"})
    else:
        print("    no auto-fixable exception in this seed — skipping single resolve")

    print("\n=== Escalate a missing settlement (honest non-fix) ===")
    exceptions = client.get("/reconcile/exceptions").json()
    missing = next((item for item in exceptions if item["mismatch_type"] == "missing_settlement"), None)
    if missing:
        r = client.post("/exceptions/resolve", json={
            "payment_id": missing["payment_id"],
            "action": "apply_fix",
        })
        check("apply_fix on missing_settlement is rejected", r.status_code == 400)
        r = client.post("/exceptions/resolve", json={
            "payment_id": missing["payment_id"],
            "action": "escalate",
            "note": "Waiting on bank UTR",
        })
        check("escalate 200", r.status_code == 200)
        check("stays open", r.json()["this_payment"]["open"] is True)
    else:
        print("    no missing_settlement in this seed — skipping escalate check")

    print("\n=== Close the books ===")
    r = client.post("/books/close")
    check("close 200", r.status_code == 200)
    report = r.json()
    check("auto_resolved is an int", isinstance(report["auto_resolved"], int))
    check("remaining_exceptions is a list", isinstance(report["remaining_exceptions"], list))
    check("final match_rate >= initial match_rate", report["final"]["match_rate"] >= report["initial"]["match_rate"] - 0.0001)
    remaining_types = {item["mismatch_type"] for item in report["remaining_exceptions"]}
    check("no auto-fixable types left in the honest list", remaining_types <= {
        "missing_settlement",
        "unclassified_discrepancy",
        "partial_settlement",
        "unknown_adjustment",
        "duplicate_settlement",
    })
    check("cash included in close report", "available_rupees" in report["cash"])
    print(f"    auto-resolved {report['auto_resolved']}, remaining {len(report['remaining_exceptions'])}")
    print(f"    final match rate {report['final']['match_rate']*100:.1f}%")

    print("\n=== Validation snapshot survives close ===")
    metrics = client.get("/reconcile/metrics").json()
    check("validation still present", "validation" in metrics)
    check("detection rate still 100% on original seed", metrics["validation"]["detection_rate"] == 1.0)

    client.post("/demo/reset")
    print("\nAll books tests passed.")


if __name__ == "__main__":
    run()
