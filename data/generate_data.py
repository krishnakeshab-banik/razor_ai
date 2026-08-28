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
from datetime import datetime, timedelta

random.seed(42)  # reproducible batch — same data every run, useful for demo + testing

NUM_RECORDS = 100
MISMATCH_RATE = 0.18   # ~18% of records get a seeded mismatch
FEE_PCT = 0.02          # Razorpay-style 2% transaction fee
TAX_PCT = 0.18          # 18% GST on the fee


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def random_datetime(start: datetime, end: datetime) -> datetime:
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def generate_batch():
    base_date = datetime(2026, 8, 1)
    records, answer_key = [], []

    for _ in range(NUM_RECORDS):
        payment_id = make_id("pay")
        order_id = make_id("order")
        amount = random.randint(50000, 500000)   # paise: Rs 500 - Rs 5000
        fee = round(amount * FEE_PCT)
        tax = round(fee * TAX_PCT)
        refund_amount = 0
        status = "captured"

        created_at = random_datetime(base_date, base_date + timedelta(days=20))
        settled_at = created_at + timedelta(days=2)

        settlement_id = make_id("setl")
        settlement_amount = amount - fee - tax - refund_amount
        mismatch_type = None

        if random.random() < MISMATCH_RATE:
            mismatch_type = random.choice([
                "missing_settlement", "unaccounted_refund",
                "fee_miscalculation", "duplicate_record", "timing_mismatch",
            ])

            if mismatch_type == "missing_settlement":
                settlement_id, settlement_amount = None, None

            elif mismatch_type == "unaccounted_refund":
                refund_amount = round(amount * random.choice([0.1, 0.25, 1.0]))
                status = "refunded" if refund_amount == amount else "partially_refunded"
                settlement_amount = amount - fee - tax   # refund wrongly excluded

            elif mismatch_type == "fee_miscalculation":
                fee = round(fee * random.choice([0.5, 1.5]))
                settlement_amount = amount - fee - tax

            elif mismatch_type == "timing_mismatch":
                settled_at = created_at + timedelta(days=random.choice([9, 12, 15]))

        row = {
            "payment_id": payment_id, "order_id": order_id, "amount": amount,
            "fee": fee, "tax": tax, "refund_amount": refund_amount,
            "settlement_id": settlement_id, "settlement_amount": settlement_amount,
            "status": status, "created_at": created_at, "settled_at": settled_at,
        }
        records.append(row)

        if mismatch_type == "duplicate_record":
            records.append(dict(row))  # deliberate duplicate row, same payment_id

        if mismatch_type:
            answer_key.append({"payment_id": payment_id, "mismatch_type": mismatch_type})

    return pd.DataFrame(records), pd.DataFrame(answer_key)


if __name__ == "__main__":
    df, answer_df = generate_batch()
    df.to_csv("synthetic_batch.csv", index=False)
    answer_df.to_csv("answer_key.csv", index=False)
    print(f"Generated {len(df)} records, {len(answer_df)} seeded mismatches")
    print(f"Mismatch breakdown:\n{answer_df['mismatch_type'].value_counts()}")
