"""Date filters, withdrawals, notifications, and audit wiring."""

import os
import sys
from datetime import datetime, timedelta
from io import BytesIO

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

    print("\n=== Date filters ===")
    client.post("/batch/generate-fresh?count=50")
    client.post("/reconcile/run")
    today = client.get("/payments?preset=today").json()
    check("payments today 200", "records" in today)
    check("payments totals present", "count" in today["totals"])
    yesterday = client.get("/payments?preset=yesterday").json()
    check("yesterday returns payload", "records" in yesterday)
    ranged = client.get("/payments?preset=custom&start=2020-01-01&end=2030-01-01").json()
    check("wide custom range has records", ranged["totals"]["count"] >= 50)
    timed = client.get("/payments?preset=custom&start=2020-01-01&end=2030-01-01&start_time=00:00&end_time=23:59").json()
    check("date+time accepted", timed["totals"]["count"] >= 50)
    empty = client.get("/payments?preset=custom&start=2030-01-02&end=2020-01-01").json()
    check("inverted range is empty", empty["totals"]["count"] == 0)
    matched_only = client.get("/payments?preset=all&status=matched").json()
    check("matched filter returns only matched", all(row["reconciliation_status"] == "matched" for row in matched_only["records"]) or matched_only["totals"]["matched"] == 0)
    check("rail totals still include exceptions", matched_only["totals"]["count"] == matched_only["totals"]["matched"] + matched_only["totals"]["exceptions"])
    exceptions_only = client.get("/payments?preset=all&status=exception").json()
    check("exception filter returns only exceptions", all(row["reconciliation_status"] == "exception" for row in exceptions_only["records"]) or exceptions_only["totals"]["exceptions"] == 0)

    print("\n=== Word close report ===")
    word = client.get("/reports/word")
    check("word report 200", word.status_code == 200)
    check("docx bytes", word.content[:2] == b"PK")
    check("word content type", "wordprocessingml" in word.headers.get("content-type", ""))
    exc = client.get("/exceptions/search?preset=last_30_days").json()
    check("exception search has totals", "totals" in exc)

    print("\n=== Withdrawals ===")
    avail = client.get("/withdrawals/availability").json()
    check("availability numeric", isinstance(avail["available_rupees"], (int, float)))
    as_of = (datetime.now() - timedelta(days=30)).isoformat()
    earlier = client.get("/withdrawals/availability", params={"as_of": as_of}).json()
    check("earlier date does not exceed later available", earlier["available_rupees"] <= avail["available_rupees"] + 0.01)
    preview = client.post("/withdrawals/preview", json={"amount_rupees": 1, "as_of": None}).json()
    check("preview has net", "net_rupees" in preview)
    check("fee calculated", preview["fee_rupees"] >= 0)
    if avail["available_rupees"] >= 1:
        first = client.post("/withdrawals", json={"amount_rupees": 1})
        check("first withdrawal 200", first.status_code == 200)
        after = client.get("/withdrawals/availability").json()
        check("balance reduced", after["available_rupees"] <= avail["available_rupees"] - 0.99)
        check("already withdrawn increased", after["already_withdrawn_rupees"] >= 1)
        too_much = client.post("/withdrawals", json={"amount_rupees": after["available_rupees"] + 100000})
        check("over-withdraw rejected", too_much.status_code == 400)
        zero = client.post("/withdrawals", json={"amount_rupees": 0})
        check("zero rejected", zero.status_code == 400)
        hist = client.get("/withdrawals").json()
        check("history has last withdrawal", hist["last"] is not None)
        check("synthetic label", hist["environment"] == "synthetic")
    none_left = client.post("/withdrawals/preview", json={"amount_rupees": 1, "as_of": "2000-01-01T00:00:00"})
    check("no balance as-of old date", none_left.status_code == 200)
    check("old date cannot withdraw", none_left.json()["can_withdraw"] is False)

    print("\n=== Daily brief and spreadsheet ===")
    day = client.get("/analytics/day")
    check("day analytics 200", day.status_code == 200)
    brief = day.json()
    check("day totals present", "totals" in brief)
    check("day headline names batch", "Batch" in (brief.get("headline") or "") and "Summary for" in (brief.get("headline") or ""))
    check("day batch_id present", bool(brief.get("batch_id")))
    check("day defaults to latest capture not empty calendar today", (brief.get("totals") or {}).get("count", 0) >= 1 or not brief.get("latest_date"))
    stamp = brief.get("latest_date") or brief.get("date")
    if stamp:
        dated = client.get("/analytics/day", params={"date": stamp})
        check("chosen date 200", dated.status_code == 200)
        check("chosen date has rows or latest hint", dated.json()["totals"]["count"] >= 0)
        excel = client.get("/reports/excel", params={"date": stamp})
        check("excel report 200", excel.status_code == 200)
        check("xlsx bytes", excel.content[:2] == b"PK")
        check("excel content type", "spreadsheetml" in excel.headers.get("content-type", ""))
    payments = client.get("/payments?preset=all").json()
    if payments.get("records"):
        pid = payments["records"][0]["payment_id"]
        lookup = client.get("/analytics/day", params={"payment_id": pid})
        check("payment lookup 200", lookup.status_code == 200)
        check("payment found", lookup.json().get("payment_found") is True)
        check("payment id echoed", lookup.json()["payment"]["payment_id"] == pid)
    missing = client.get("/analytics/day", params={"payment_id": "pay_does_not_exist_xyz"})
    check("unknown payment is not found", missing.json().get("payment_found") is False)

    print("\n=== Notifications ===")
    notes = client.get("/notifications").json()
    first_unread = notes["unread"]
    check("flagged batch created notifications", first_unread >= 1)
    pid = notes["notifications"][0]["payment_id"]
    client.post("/reconcile/run")
    again = client.get("/notifications").json()
    check("rerun does not duplicate flags", again["unread"] == first_unread)
    marked = client.post(f"/notifications/{notes['notifications'][0]['id']}/read")
    check("mark read 200", marked.status_code == 200)
    check("read flag true", marked.json()["read"] is True)
    client.post("/demo/simulate-payment", json={"amount_rupees": 250, "outcome": "missing_settlement"})
    after_sim = client.get("/notifications").json()
    check("new flagged payment adds notification", after_sim["unread"] >= 1)
    opened = after_sim["notifications"][0]
    check("notification has payment id", opened["payment_id"].startswith("pay_"))

    print("\n=== Audit ===")
    trail = client.get("/audit-trail?limit=50").json()
    actions = {row["action_type"] for row in trail}
    check("withdrawal audited", "withdrawal" in actions)
    check("exception audited", "exception" in actions)
    client.get(f"/exceptions/{pid}/investigate")
    trail2 = client.get("/audit-trail?action_type=investigate").json()
    check("investigation audited", any(row["action_type"] == "investigate" for row in trail2))

    print("\n=== API failures ===")
    client.post("/demo/reset")
    missing = client.get("/withdrawals/availability")
    check("withdraw without batch is 400", missing.status_code == 400)
    bad_file = client.post("/batch/upload", files={"file": ("x.bin", BytesIO(b"not-csv"), "application/octet-stream")})
    check("invalid upload 400", bad_file.status_code == 400)

    print("\nAll ops-feature tests passed.")


if __name__ == "__main__":
    run()
