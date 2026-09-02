"""
End-to-end test of the FastAPI backend, hitting every endpoint the same way
a frontend would. Uses FastAPI's TestClient, so it doesn't need a running
server or real network calls (except /chat, which is skipped here since it
needs a live GEMINI_API_KEY -- see test_chatbot_live.py for that).

Run: python tests/test_api.py
(run from the razor-ai/ root directory, after generate_data.py has been run)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))  # so relative paths in main.py resolve

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        raise AssertionError(label)


def run():
    print("=== POST /demo/reset (clean slate) ===")
    r = client.post("/demo/reset")
    check("reset returns 200", r.status_code == 200)

    print("\n=== GET / (root) ===")
    r = client.get("/")
    check("root returns 200", r.status_code == 200)
    check("root reports ok status", r.json().get("status") == "ok")

    print("\n=== GET /reconcile/metrics before any batch loaded (should fail cleanly) ===")
    r = client.get("/reconcile/metrics")
    check("returns 400, not a 500 crash", r.status_code == 400)

    print("\n=== POST /batch/load ===")
    r = client.post("/batch/load")
    check("load returns 200", r.status_code == 200)
    check("loaded count > 50 (track requires 50+ records)", r.json()["loaded"] >= 50)
    print(f"    Loaded {r.json()['loaded']} records")

    print("\n=== POST /reconcile/run ===")
    r = client.post("/reconcile/run")
    check("reconcile returns 200", r.status_code == 200)
    metrics = r.json()
    check("match_rate is present", "match_rate" in metrics)
    check("validation block present (answer key comparison)", "validation" in metrics)
    check("mismatch_breakdown present", isinstance(metrics.get("mismatch_breakdown"), dict))
    print(f"    Match rate: {metrics['match_rate']*100:.1f}%, exceptions: {metrics['exceptions']}")
    if "validation" in metrics:
        v = metrics["validation"]
        print(f"    Validation: {v['correctly_detected']}/{v['seeded_mismatches']} seeded "
              f"mismatches detected, {v['false_positives']} false positives")
        check("detection rate is 100%", v["detection_rate"] == 1.0)

    print("\n=== GET /reconcile/metrics (after run) ===")
    r = client.get("/reconcile/metrics")
    check("metrics returns 200", r.status_code == 200)

    print("\n=== GET /reconcile/exceptions ===")
    r = client.get("/reconcile/exceptions")
    check("exceptions returns 200", r.status_code == 200)
    exceptions = r.json()
    check("exceptions is a non-empty list", len(exceptions) > 0)
    check("each exception has an explanation", all("explanation" in e for e in exceptions))
    check("each exception has a suggested action", all("suggested_action" in e for e in exceptions))
    check("no exception explanation has unfilled placeholders",
          all("{" not in e["explanation"] for e in exceptions))
    print(f"    {len(exceptions)} exceptions returned, all with explanations")

    print("\n=== POST /batch/upload (CSV file upload) ===")
    upload_file = ("demo_batch.csv", b"payment_id,amount,order_id,settlement_date,bank_ref,source,notes\npay_1,10000,order_1,2026-08-19,BNK_1,Razorpay,Settlement expected within 2 days\npay_2,20000,order_2,2026-08-20,BNK_2,Razorpay,Missing settlement record\n", "text/csv")
    r = client.post("/batch/upload", files={"file": upload_file})
    check("upload returns 200", r.status_code == 200)
    check("upload loads rows into the batch", r.json()["loaded"] >= 2)

    print("\n=== GET /audit-trail ===")
    r = client.get("/audit-trail")
    check("audit trail returns 200", r.status_code == 200)
    audit = r.json()
    check("audit trail has entries", len(audit) > 0)
    check("audit trail includes rule_engine entries", any(a["source"] == "rule_engine" for a in audit))
    print(f"    {len(audit)} audit entries logged")

    print("\n=== GET /analytics/summary ===")
    r = client.get("/analytics/summary")
    check("analytics summary returns 200", r.status_code == 200)
    analytics = r.json()
    check("summary contains total_orders", "total_orders" in analytics)
    check("summary contains total_earnings", "total_earnings" in analytics)
    check("summary contains monthly breakdown", isinstance(analytics.get("monthly"), list) and len(analytics["monthly"]) > 0)
    check("summary contains yearly breakdown", isinstance(analytics.get("yearly"), list) and len(analytics["yearly"]) > 0)
    print(f"    Orders: {analytics['total_orders']}, earnings: Rs {analytics['total_earnings']}")

    print("\n=== POST /chat (SKIPPED -- needs live GEMINI_API_KEY, see test_chatbot_live.py) ===")

    print("\n=== POST /demo/reset (cleanup) ===")
    r = client.post("/demo/reset")
    check("reset returns 200", r.status_code == 200)
    r = client.get("/reconcile/metrics")
    check("metrics correctly unavailable after reset", r.status_code == 400)

    print("\nAll API tests passed.")


if __name__ == "__main__":
    run()
