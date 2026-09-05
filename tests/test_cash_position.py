"""
In-transit stock and the 7-day forecast must be independent.

In-transit = matched, not yet received (any future settled_at).
Next 7 days = only that slice dated inside the coming week.

Run: python tests/test_cash_position.py
"""

import os
import sys
from datetime import timedelta

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "data"))

from cash import compute_cash_position
from config import now_ist
from generate_data import generate_batch
from reconciliation import reconcile


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        raise AssertionError(label)


def test_formulas_are_not_aliases():
    now = now_ist()
    rows = [
        {
            "payment_id": "pay_avail01",
            "amount": 100000,
            "fee": 2000,
            "tax": 360,
            "refund_amount": 0,
            "settlement_amount": 97640,
            "settlement_id": "setl_avail01",
            "reconciliation_status": "matched",
            "created_at": now - timedelta(days=10),
            "settled_at": now - timedelta(days=8),
        },
        {
            "payment_id": "pay_week01",
            "amount": 200000,
            "fee": 4000,
            "tax": 720,
            "refund_amount": 0,
            "settlement_amount": 195280,
            "settlement_id": "setl_week01",
            "reconciliation_status": "matched",
            "created_at": now - timedelta(hours=8),
            "settled_at": now + timedelta(days=2),
        },
        {
            "payment_id": "pay_later01",
            "amount": 300000,
            "fee": 6000,
            "tax": 1080,
            "refund_amount": 0,
            "settlement_amount": 292920,
            "settlement_id": "setl_later01",
            "reconciliation_status": "matched",
            "created_at": now - timedelta(days=1),
            "settled_at": now + timedelta(days=12),
        },
        {
            "payment_id": "pay_block01",
            "amount": 80000,
            "fee": 1600,
            "tax": 288,
            "refund_amount": 0,
            "expected_settlement": 78112,
            "settlement_amount": 0,
            "settlement_id": None,
            "reconciliation_status": "exception",
            "created_at": now - timedelta(days=3),
            "settled_at": now + timedelta(days=2),
        },
    ]
    position = compute_cash_position(pd.DataFrame(rows), as_of=now)
    check("available is the past matched settlement", position["available_rupees"] == 976.40)
    check("in-transit includes this week and beyond", position["in_transit_rupees"] == 4882.00)
    check("next 7 days is only the dated-this-week slice", position["expected_7d_rupees"] == 1952.80)
    check("the two KPIs are not equal", position["in_transit_rupees"] != position["expected_7d_rupees"])
    check("blocked stays out of both inflows", position["blocked_rupees"] == 781.12)


def test_fresh_batch_shows_independent_kpis():
    for seed in (7, 11, 19, 42):
        raw, _key = generate_batch(num_records=100, seed=seed)
        position = compute_cash_position(reconcile(raw))
        check(f"seed {seed} has in-transit", position["in_transit_rupees"] > 0)
        check(f"seed {seed} has a 7-day inflow", position["expected_7d_rupees"] > 0)
        check(
            f"seed {seed} in-transit > next 7 days",
            position["in_transit_rupees"] > position["expected_7d_rupees"],
        )


def run():
    print("=== Cash KPI independence ===")
    test_formulas_are_not_aliases()
    test_fresh_batch_shows_independent_kpis()
    print("\nAll cash position checks passed.")


if __name__ == "__main__":
    run()
