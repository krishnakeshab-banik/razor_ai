"""
Generates a synthetic batch of Razorpay-shaped transaction records for Razor-AI.
Deliberately seeds ~18% of records with a known mismatch type, and writes a
separate hidden answer key so the reconciliation engine's accuracy can be
measured against ground truth (not just eyeballed).

Run: python generate_data.py
Output: synthetic_batch.csv (input to the reconciliation engine)
        answer_key.csv       (ground truth — do NOT feed this to the engine)
"""

import pandas as pd
import random
import uuid
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))


def _now() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)

NUM_RECORDS = 100
MISMATCH_RATE = 0.18   # ~18% of records get a seeded mismatch
FEE_PCT = 0.02          # Razorpay-style 2% transaction fee
TAX_PCT = 0.18          # 18% GST on the fee


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def random_datetime(start: datetime, end: datetime, rng: random.Random) -> datetime:
    delta = end - start
    return start + timedelta(seconds=rng.randint(0, int(delta.total_seconds())))


def ensure_independent_cash_lanes(df: pd.DataFrame, now: Optional[datetime] = None) -> pd.DataFrame:
    """
    Keep in-transit stock and the 7-day forecast from collapsing into one number.

    In-transit is every matched settlement not yet received. Next 7 days is only
    the slice dated inside that week. A pure T+2 tail makes those equal, which
    looks like a copy-paste bug on the Cash page.
    """
    if df is None or getattr(df, "empty", True):
        return df
    now = now or _now()
    out = df.copy()
    out["created_at"] = pd.to_datetime(out["created_at"], errors="coerce")
    out["settled_at"] = pd.to_datetime(out["settled_at"], errors="coerce")
    created = out["created_at"]
    settled = out["settled_at"]
    delta_days = (settled - created).dt.total_seconds() / 86400.0
    has_settlement = out["settlement_id"].notna() if "settlement_id" in out.columns else True
    clean = has_settlement & created.notna() & settled.notna() & delta_days.between(1.4, 2.6)
    idxs = list(out.index[clean])
    if len(idxs) < 4:
        idxs = list(out.index[has_settlement & created.notna()])
    if len(idxs) < 4:
        return out

    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Two land inside the 7 calendar-day forecast. Two settle on day +7, which is
    # still matched (created→settled ≤ 7 days) but outside that window.
    beyond = day0 + timedelta(days=7, hours=15)
    stamps = (
        (now - timedelta(hours=8), now + timedelta(days=2)),
        (now - timedelta(hours=20), now + timedelta(days=1)),
        (beyond - timedelta(days=7), beyond),
        (beyond - timedelta(days=6, hours=18), beyond + timedelta(hours=4)),
    )
    for idx, (created_at, settled_at) in zip(idxs[:4], stamps):
        out.at[idx, "created_at"] = created_at
        out.at[idx, "settled_at"] = settled_at
    return out


def generate_batch(num_records: int = NUM_RECORDS, seed: Optional[int] = None):
    rng = random.Random(seed)
    # Spread captures across ~8 months so reports have monthly/yearly series,
    # while keeping a recent T+2 tail for in-transit cash.
    now = _now()
    horizon_start = now - timedelta(days=260)
    records, answer_key = [], []

    for _ in range(num_records):
        payment_id = make_id("pay")
        order_id = make_id("order")
        amount = rng.randint(50000, 500000)   # paise: Rs 500 - Rs 5000
        fee = round(amount * FEE_PCT)
        tax = round(fee * TAX_PCT)
        refund_amount = 0
        status = "captured"

        created_at = random_datetime(horizon_start, now - timedelta(hours=4), rng)
        settled_at = created_at + timedelta(days=2)

        settlement_id = make_id("setl")
        settlement_amount = amount - fee - tax - refund_amount
        adjustment = 0
        mismatch_type = None
        customer_id = make_id("cust")

        if rng.random() < MISMATCH_RATE:
            mismatch_type = rng.choice([
                "missing_settlement", "unaccounted_refund",
                "fee_miscalculation", "tax_line_mismatch", "duplicate_record", "timing_mismatch",
                "partial_settlement", "unknown_adjustment",
            ])

            if mismatch_type == "missing_settlement":
                settlement_id, settlement_amount = None, None

            elif mismatch_type == "unaccounted_refund":
                refund_amount = round(amount * rng.choice([0.1, 0.25, 1.0]))
                status = "refunded" if refund_amount == amount else "partially_refunded"
                settlement_amount = amount - fee - tax   # refund wrongly excluded

            elif mismatch_type == "fee_miscalculation":
                fee = round(fee * rng.choice([0.5, 1.5]))
                settlement_amount = amount - fee - tax

            elif mismatch_type == "tax_line_mismatch":
                tax = round(fee * 0.42)
                settlement_amount = amount - fee - tax

            elif mismatch_type == "timing_mismatch":
                settled_at = created_at + timedelta(days=rng.choice([9, 12, 15]))

            elif mismatch_type == "partial_settlement":
                settlement_amount = round((amount - fee - tax) * 0.55)

            elif mismatch_type == "unknown_adjustment":
                adjustment = round(amount * 0.04)
                settlement_amount = amount - fee - tax - refund_amount - adjustment

        row = {
            "payment_id": payment_id, "order_id": order_id, "customer_id": customer_id,
            "amount": amount, "fee": fee, "tax": tax, "refund_amount": refund_amount,
            "adjustment": adjustment,
            "settlement_id": settlement_id, "settlement_amount": settlement_amount,
            "utr": settlement_id, "currency": "INR",
            "status": status, "created_at": created_at, "settled_at": settled_at,
            "payment_method": rng.choice(["upi", "card", "netbanking", "wallet"]),
            "gstin": "29AABCU9603R1ZX",
            "source": "razorpay",
            "description": f"Razorpay capture {payment_id}",
        }
        records.append(row)

        if mismatch_type == "duplicate_record":
            records.append(dict(row))  # deliberate duplicate row, same payment_id

        if mismatch_type:
            answer_key.append({"payment_id": payment_id, "mismatch_type": mismatch_type})

    df = ensure_independent_cash_lanes(pd.DataFrame(records), now)
    return df, pd.DataFrame(answer_key)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    df, answer_df = generate_batch(seed=None)
    df.to_csv(os.path.join(here, "synthetic_batch.csv"), index=False)
    answer_df.to_csv(os.path.join(here, "answer_key.csv"), index=False)
    print(f"Generated {len(df)} records, {len(answer_df)} seeded mismatches")
    print(f"Mismatch breakdown:\n{answer_df['mismatch_type'].value_counts()}")
