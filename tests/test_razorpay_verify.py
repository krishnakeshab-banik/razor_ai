"""
Tests POST /demo/razorpay/create-order and /demo/razorpay/verify.

Uses dummy env credentials and a mocked Razorpay client so CI never
calls the live API or needs real keys. HMAC verification is mandatory:
an unverified callback must not be ingested.

Run: python tests/test_razorpay_verify.py
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))

TEST_KEY_ID = "rzp_test_dummy_id"
TEST_KEY_SECRET = "dummy_secret_for_hmac_tests_only"

os.environ["RAZORPAY_KEY_ID"] = TEST_KEY_ID
os.environ["RAZORPAY_KEY_SECRET"] = TEST_KEY_SECRET

from fastapi.testclient import TestClient
from demo_payment import map_razorpay_payment
import main
import razorpay_gateway

client = TestClient(main.app)


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        raise AssertionError(label)


def sign(order_id: str, payment_id: str) -> str:
    return hmac.new(
        TEST_KEY_SECRET.encode("utf-8"),
        f"{order_id}|{payment_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


FAKE_PAYMENT = {
    "id": "pay_testRealId",
    "amount": 150000,
    "order_id": "order_test123",
    "created_at": 1700000000,
    "method": "card",
    "status": "captured",
    "fee": 0,
    "tax": 0,
}


def fake_create_order(amount_paise, notes=None):
    return {"id": "order_test123", "amount": amount_paise, "currency": "INR"}


def fake_fetch_payment(payment_id):
    return {**FAKE_PAYMENT, "id": payment_id}


def run():
    print("=== map_razorpay_payment keeps real ids ===")
    rows = map_razorpay_payment(FAKE_PAYMENT, "clean")
    check("one row for clean", len(rows) == 1)
    check("uses Razorpay payment_id", rows[0]["payment_id"] == "pay_testRealId")
    check("uses Razorpay order_id", rows[0]["order_id"] == "order_test123")
    check("uses Razorpay amount", rows[0]["amount"] == 150000)
    check("uses Razorpay method", rows[0]["payment_method"] == "card")

    print("\n=== POST /demo/reset ===")
    client.post("/demo/reset")

    print("\n=== create-order without keys returns 503 ===")
    saved_id = os.environ.pop("RAZORPAY_KEY_ID", None)
    saved_secret = os.environ.pop("RAZORPAY_KEY_SECRET", None)
    try:
        r = client.post("/demo/razorpay/create-order", json={"amount_rupees": 100, "outcome": "clean"})
        check("503 when keys missing", r.status_code == 503)
    finally:
        if saved_id is not None:
            os.environ["RAZORPAY_KEY_ID"] = saved_id
        if saved_secret is not None:
            os.environ["RAZORPAY_KEY_SECRET"] = saved_secret

    print("\n=== create-order with mocked SDK ===")
    razorpay_gateway.create_order = fake_create_order
    r = client.post("/demo/razorpay/create-order", json={
        "amount_rupees": 1500,
        "outcome": "missing_settlement",
        "customer_name": "Judge",
        "customer_email": "judge@example.com",
        "payment_method": "Card",
        "items": [{"id": "sku-1", "name": "Notebook", "qty": 1, "price": 1500}],
    })
    check("create-order returns 200", r.status_code == 200)
    body = r.json()
    check("returns order_id", body["order_id"] == "order_test123")
    check("returns public key_id only", body["key_id"] == TEST_KEY_ID)
    check("does not leak a secret field", "key_secret" not in body and "secret" not in body)

    print("\n=== verify rejects a bad signature and does not ingest ===")
    razorpay_gateway.fetch_payment = fake_fetch_payment
    r = client.post("/demo/razorpay/verify", json={
        "razorpay_order_id": "order_test123",
        "razorpay_payment_id": "pay_testRealId",
        "razorpay_signature": "deadbeef",
    })
    check("bad signature returns 400", r.status_code == 400)
    audit = client.get("/audit-trail").json()
    check("unverified callback is not audited as razorpay_test_api",
          not any(a["source"] == "razorpay_test_api" for a in audit))

    print("\n=== verify with valid HMAC ingests through the engine ===")
    r = client.post("/demo/razorpay/verify", json={
        "razorpay_order_id": "order_test123",
        "razorpay_payment_id": "pay_testRealId",
        "razorpay_signature": sign("order_test123", "pay_testRealId"),
    })
    check("verify returns 200", r.status_code == 200)
    payment = r.json()["this_payment"]
    check("real payment_id is kept", payment["payment_id"] == "pay_testRealId")
    check("planted outcome is missing_settlement", payment["mismatch_type"] == "missing_settlement")
    check("flagged as exception", payment["reconciliation_status"] == "exception")

    audit = client.get("/audit-trail").json()
    check("audit source is razorpay_test_api",
          any(a["source"] == "razorpay_test_api" for a in audit))
    check("audit source is not gemini_api",
          all(a["source"] != "gemini_api" for a in audit if a.get("record_ids") == "pay_testRealId"))

    orders = client.get("/demo/orders").json()["orders"]
    check("store order was created", any(o["payment_id"] == "pay_testRealId" for o in orders))

    print("\n=== simulate-payment still works alongside ===")
    r = client.post("/demo/simulate-payment", json={"amount_rupees": 500, "outcome": "clean"})
    check("synthetic path still 200", r.status_code == 200)
    check("synthetic payment_id is generated, not the Razorpay id",
          r.json()["this_payment"]["payment_id"] != "pay_testRealId")

    client.post("/demo/reset")
    print("\nAll Razorpay verify tests passed.")


if __name__ == "__main__":
    run()
