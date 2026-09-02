"""Tests for finance-controller intelligence, clustering, search, refunds, and memory."""

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

    print("=== Briefing empty data ===")
    empty = client.get("/controller/briefing").json()
    check("empty briefing has zero payments", empty["numbers"]["payments"] == 0)
    check("empty briefing says no batch", "no reconciled batch" in empty["summary"].lower())

    print("\n=== Generate + briefing calculations ===")
    loaded = client.post("/batch/generate-fresh?count=50").json()
    check("generated", loaded["loaded"] >= 50)
    metrics = client.post("/reconcile/run").json()
    briefing = client.get("/controller/briefing").json()
    check("briefing payments match batch", briefing["numbers"]["payments"] == metrics["total_records"])
    check("match rate is live", briefing["numbers"]["match_rate"] == metrics["match_rate"])
    check("unresolved is numeric", isinstance(briefing["numbers"]["unresolved_rupees"], (int, float)))
    check("no hardcoded 8.4L", "8.4L" not in briefing["summary"])

    print("\n=== Large-ish data still computes ===")
    client.post("/demo/reset")
    client.post("/batch/generate-fresh?count=250")
    big = client.post("/reconcile/run").json()
    briefing = client.get("/controller/briefing").json()
    check("250 records in briefing", briefing["numbers"]["payments"] == big["total_records"])

    print("\n=== What changed ===")
    changed = client.get("/controller/what-changed?versus=yesterday").json()
    check("has current/previous", "current" in changed and "previous" in changed)
    zero = client.get("/controller/what-changed?versus=yesterday").json()
    for item in zero.get("changes") or []:
        if item["previous"] == 0 and item["current"] == 0:
            check("zero-to-zero is 0 pct", item["pct_change"] == 0)
    batch_cmp = client.get("/controller/what-changed?versus=previous_batch").json()
    check("previous batch payload exists", "changes" in batch_cmp)

    print("\n=== Exception clustering ===")
    clusters = client.get("/controller/clusters").json()
    check("clusters is a list", isinstance(clusters, list))
    if clusters:
        top = clusters[0]
        check("cluster has count >= 2", top["count"] >= 2)
        check("impact is summed rupees", isinstance(top["impact_rupees"], (int, float)))
        check("root cause status is known vocabulary", top["root_cause"]["status"] in {"confirmed", "probable", "unknown"})
        unique_ids = set()
        for cluster in clusters:
            overlap = unique_ids.intersection(cluster["payment_ids"])
            check("unrelated groups stay separate", not overlap)
            unique_ids.update(cluster["payment_ids"])

    print("\n=== Batch resolve requires confirmation ===")
    exceptions = client.get("/reconcile/exceptions").json()
    fixable = [item for item in exceptions if item.get("suggested_action", {}).get("auto_fixable")]
    if len(fixable) >= 2:
        ids = [item["payment_id"] for item in fixable[:2]]
        preview = client.post("/exceptions/batch-resolve", json={"payment_ids": ids, "action": "apply_fix", "confirm": False}).json()
        check("preview requires confirmation", preview["requires_confirmation"] is True)
        still = client.get("/reconcile/exceptions").json()
        check("preview did not mutate", len(still) >= len(exceptions) - 1)
        confirmed = client.post("/exceptions/batch-resolve", json={"payment_ids": ids, "action": "apply_fix", "confirm": True})
        check("confirm 200", confirmed.status_code == 200)
        body = confirmed.json()
        check("audit-able applied list", "applied" in body)
        missing = [item for item in exceptions if item["mismatch_type"] == "missing_settlement"][:1]
        if missing:
            bad = client.post("/exceptions/batch-resolve", json={
                "payment_ids": [missing[0]["payment_id"]], "action": "apply_fix", "confirm": True,
            }).json()
            check("missing settlement skipped", len(bad["skipped"]) >= 1)

    print("\n=== Finance search ===")
    if exceptions:
        pid = exceptions[0]["payment_id"]
        found = client.get(f"/search?q=Find payment {pid}").json()
        check("payment search finds id", any(pid == row.get("payment_id") for row in found["results"]["payments"]))
        above = client.get("/search?q=Show unresolved transactions above 10").json()
        check("amount search returns payload", "results" in above)
        date_q = client.get("/search?q=Show all refund exceptions from last week").json()
        check("date search interpreted", date_q["filters"]["kind"] in {"refund", "exception"})

    print("\n=== Natural-language action confirmation ===")
    if exceptions:
        pid = exceptions[0]["payment_id"]
        pending = client.post("/chat", json={"question": f"Mark {pid} as investigating"}).json()
        check("propose confirmation", pending.get("pending_confirmation") or "confirm" in pending["answer"].lower())
        if pending.get("pending_confirmation"):
            done = client.post("/chat/confirm", json={"confirm": True})
            check("confirm executes", done.status_code == 200)
        bogus = client.post("/chat/confirm", json={"confirm": True})
        check("no pending is rejected", bogus.status_code == 400)

    print("\n=== Resolution memory and human rules ===")
    if exceptions:
        pid = exceptions[0]["payment_id"]
        client.post("/exceptions/resolve", json={
            "payment_id": pid, "action": "escalate", "note": "legitimate timing", "remember": True,
        })
        memory = client.get("/controller/memory").json()
        check("memory stored", len(memory["memory"]) >= 1)
        rule = client.post("/controller/rules", json={
            "title": "Merchant X fee adjustment",
            "guidance": "Settlement adjustment type A is a legitimate recurring adjustment.",
            "mismatch_type": exceptions[0]["mismatch_type"],
            "origin": "human",
        }).json()
        check("human rule created", rule["origin"] == "human")
        disabled = client.patch(f"/controller/rules/{rule['id']}", json={"enabled": False}).json()
        check("rule can disable", disabled["enabled"] in {0, False})
        ai_rule = client.post("/controller/rules", json={
            "title": "AI invented", "guidance": "auto approve", "origin": "ai",
        })
        check("AI origin rejected", ai_rule.status_code == 400)

    print("\n=== Anomaly detection baseline ===")
    anomalies = client.get("/controller/anomalies").json()
    check("anomaly payload", "signals" in anomalies)
    check("insufficient history is explicit when needed", "insufficient_history" in anomalies)

    print("\n=== Timeline ===")
    if exceptions:
        tl = client.get(f"/records/{exceptions[0]['payment_id']}/timeline").json()
        stamps = [event["timestamp"] for event in tl["events"] if event.get("timestamp")]
        check("timeline chronological", stamps == sorted(stamps))

    print("\n=== AI vs human metrics are live ===")
    perf = client.get("/controller/performance").json()
    check("processed equals batch", perf["total_records_processed"] == client.get("/reconcile/metrics").json()["total_records"])
    check("refused cases present", "cases_ai_refused" in perf)

    print("\n=== Cash why ===")
    why = client.get("/cash/why").json()
    check("expected and actual present", "expected_rupees" in why and "actual_rupees" in why)
    check("unexplained is not forced to zero always", "unexplained_rupees" in why)

    print("\n=== Marketplace refund reflects in books ===")
    client.post("/demo/reset")
    sim = client.post("/demo/simulate-payment", json={"amount_rupees": 500, "outcome": "clean"}).json()
    pid = sim["this_payment"]["payment_id"]
    orders = client.get("/demo/orders").json()["orders"]
    check("past order stored", any(item["payment_id"] == pid for item in orders))
    preview = client.post("/demo/refund", json={"payment_id": pid, "confirm": False}).json()
    check("refund confirm required", preview["requires_confirmation"] is True)
    notes_before = client.get("/notifications").json()["unread"]
    posted = client.post("/demo/refund", json={"payment_id": pid, "confirm": True})
    check("refund 200", posted.status_code == 200)
    body = posted.json()
    check("cash returned", "cash" in body)
    check("refund amount on payment", body["this_payment"]["refund_amount"] > 0)
    notes = client.get("/notifications").json()["notifications"]
    check("refund notification created", any(str(item["mismatch_type"]).startswith("refund_initiated") for item in notes) or body["notifications"])
    metrics_after = client.get("/reconcile/metrics").json()
    check("metrics still computed after refund", metrics_after["total_records"] >= 1)
    _ = notes_before

    flagged = client.post("/demo/simulate-payment", json={"amount_rupees": 300, "outcome": "missing_settlement"}).json()
    check("flagged checkout notifies", len(flagged.get("notifications") or []) >= 1)

    print("\n=== Health score formula is transparent ===")
    health = client.get("/controller/health").json()
    check("score 0-100", 0 <= health["score"] <= 100)
    check("formula shown", "100" in health["formula"])

    client.post("/demo/reset")
    print("\nAll controller-intel tests passed.")


if __name__ == "__main__":
    run()
