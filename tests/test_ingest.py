"""Ingest mapping, rupee-vs-paise detection, and malformed-row handling."""

import os
import sys
from io import BytesIO

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from ingest import detect_source_type, inspect_bytes, normalize_batch


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        raise AssertionError(label)


def run():
    print("=== Column mapping ===")
    raw = pd.DataFrame({
        "paymentid": ["pay_map01"],
        "gmv": [99.50],
        "gst": [0.36],
        "processing_fee": [1.99],
        "bank_utr": ["UTR123"],
        "net_settlement_amount": [97.15],
        "createddate": ["2026-01-02"],
    })
    normalized, report = normalize_batch(raw)
    check("maps paymentid to payment_id", "payment_id" in normalized.columns)
    check("maps gmv to amount", "amount" in normalized.columns)
    check("maps gst to tax", "tax" in normalized.columns)
    check("maps processing_fee to fee", "fee" in normalized.columns)
    check("maps bank_utr to utr", "utr" in normalized.columns)
    check("rupees converted to paise", report["units"] == "rupees_converted_to_paise")
    check("99.50 became 9950 paise", int(normalized.loc[0, "amount"]) == 9950)

    print("=== Source typing ===")
    check("combined export", detect_source_type(["payment_id", "settlement_id"]) == "combined_razorpay_export")
    check("payments hint", detect_source_type(["payment_id", "amount", "order_id"]) == "payments")

    print("=== Malformed rows are kept ===")
    messy = pd.DataFrame({
        "payment_id": ["pay_ok", "pay_bad"],
        "amount": [150000, "not-a-number"],
        "fee": [3000, 0],
        "tax": [540, 0],
        "refund_amount": [0, 0],
        "settlement_id": ["setl_1", "setl_2"],
        "settlement_amount": [146460, 0],
    })
    kept, messy_report = normalize_batch(messy)
    check("both rows kept", len(kept) == 2)
    check("malformed row flagged", any(item["field"] == "amount" for item in messy_report["malformed_rows"]))
    check("bad amount became 0 not dropped", float(kept.loc[kept["payment_id"] == "pay_bad", "amount"].iloc[0]) == 0)

    print("=== inspect_bytes ===")
    csv = b"payment_id,amount,fee,tax\npay_a,10000,200,36\n"
    frame, meta = inspect_bytes(csv, "batch.csv")
    check("csv parsed", len(frame) == 1)
    check("row count in meta", meta["rows"] == 1)
    try:
        inspect_bytes(b"", "empty.csv")
        check("empty file rejected", False)
    except ValueError:
        check("empty file rejected", True)
    try:
        inspect_bytes(b"not-a-spreadsheet", "notes.bin")
        check("unsupported type rejected", False)
    except ValueError as exc:
        check("unsupported type rejected", "unsupported" in str(exc).lower())

    print("=== Missing payment_id warning ===")
    no_id = pd.DataFrame({"gmv": [12.00], "fee": [0.24], "tax": [0.04]})
    filled, warn_report = normalize_batch(no_id)
    check("temporary payment_id assigned", str(filled.loc[0, "payment_id"]).startswith("pay_"))
    check("warning recorded", any("payment_id" in item for item in warn_report["warnings"]))

    print("\nAll ingest tests passed.")


if __name__ == "__main__":
    run()
