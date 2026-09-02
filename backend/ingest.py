"""
CSV / XLSX ingest with column detection, validation, and source typing.

Does not silently drop invalid rows. Malformed rows are kept, flagged, and
reported so finance can see exactly what failed.
"""

from __future__ import annotations

import os
from io import BytesIO

import pandas as pd

from config import FEE_PCT, MAX_UPLOAD_BYTES, MAX_UPLOAD_ROWS, TAX_PCT

COLUMN_MAP = {
    "payment_id": ["payment_id", "paymentid", "transaction_id", "txn_id"],
    "order_id": ["order_id", "orderid", "merchant_order_id", "invoice_id"],
    "customer_id": ["customer_id", "customerid", "cust_id"],
    "amount": ["amount", "transaction_amount", "gross_amount", "gmv"],
    "fee": ["fee", "processing_fee", "charges", "fee_amount"],
    "tax": ["tax", "gst", "tax_amount"],
    "refund_amount": ["refund_amount", "refunds", "refund"],
    "adjustment": ["adjustment", "adjustments", "other_adjustment"],
    "settlement_id": ["settlement_id", "settlementid", "bank_ref", "reference_id"],
    "settlement_amount": ["settlement_amount", "net_settlement_amount", "settled_amount", "net_amount"],
    "utr": ["utr", "bank_utr", "utr_number"],
    "status": ["status", "payment_status"],
    "created_at": ["created_at", "createddate", "transaction_date", "payment_date", "date_created"],
    "settled_at": ["settled_at", "settlement_date", "settled_date", "settlement_at"],
    "payment_method": ["payment_method", "method", "mode"],
    "gstin": ["gstin", "gst_in", "tax_id"],
    "source": ["source", "gateway", "origin"],
    "currency": ["currency", "ccy"],
    "description": ["description", "narration", "remarks"],
}

SOURCE_HINTS = {
    "payments": {"payment_id", "amount", "order_id"},
    "settlements": {"settlement_id", "utr", "net_amount", "settlement_amount"},
    "bank": {"bank_transaction_id", "utr", "transaction_type"},
    "refunds": {"refund_id", "refund_amount"},
    "fees": {"fee_amount", "fee_type"},
    "tax": {"tax_type", "taxable_amount"},
    "invoices": {"invoice_id", "expected_amount"},
}

REQUIRED_FOR_RECONCILE = ["payment_id", "amount"]


def _amounts_look_like_rupees(series: pd.Series) -> bool:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return False
    has_fraction = bool(((numeric % 1) != 0).any())
    median = float(numeric.median())
    return has_fraction or median < 10000


def detect_source_type(columns: list[str]) -> str:
    lowered = {str(col).strip().lower() for col in columns}
    scores = {name: len(hints & lowered) for name, hints in SOURCE_HINTS.items()}
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    if "settlement_id" in lowered and "payment_id" in lowered:
        return "combined_razorpay_export"
    return "combined_razorpay_export"


def inspect_bytes(contents: bytes, filename: str) -> tuple[pd.DataFrame, dict]:
    if len(contents) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not contents:
        raise ValueError("File is empty.")

    filename = (filename or "upload.csv").lower()
    ext = os.path.splitext(filename)[1].lstrip(".")
    allowed = {"csv", "txt", "xls", "xlsx"}
    if ext not in allowed:
        raise ValueError("Unsupported file type. Please upload CSV, TXT, XLS, or XLSX.")

    buffer = BytesIO(contents)
    try:
        if ext in {"csv", "txt"}:
            df = pd.read_csv(buffer)
        else:
            df = pd.read_excel(buffer, engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Unable to parse uploaded file: {exc}") from exc

    if df.empty:
        raise ValueError("The file has a header but no data rows.")
    if len(df) > MAX_UPLOAD_ROWS:
        raise ValueError(f"File has {len(df)} rows. Demo limit is {MAX_UPLOAD_ROWS}.")
    return df, {
        "filename": filename,
        "rows": int(len(df)),
        "columns": [str(col) for col in df.columns],
        "detected_source": detect_source_type(list(df.columns)),
    }


def normalize_batch(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Maps an uploaded or generated frame into the engine schema.
    Returns (normalized_df, validation_report).
    """
    raw_columns = [str(col) for col in df.columns]
    detected_source = detect_source_type(raw_columns)
    report = {
        "detected_source": detected_source,
        "detected_columns": raw_columns,
        "mapped_columns": {},
        "missing_required": [],
        "malformed_rows": [],
        "warnings": [],
        "row_count": int(len(df)),
        "units": "paise",
        "preview": [],
    }

    normalized = df.copy()
    normalized.columns = [str(col).strip() for col in normalized.columns]
    lower_map = {col.lower(): col for col in normalized.columns}
    for canonical, aliases in COLUMN_MAP.items():
        for alias in aliases:
            actual = lower_map.get(alias.lower())
            if actual is not None:
                normalized[canonical] = normalized[actual]
                report["mapped_columns"][canonical] = actual
                break

    for required in REQUIRED_FOR_RECONCILE:
        if required not in normalized.columns:
            report["missing_required"].append(required)

    if "payment_id" not in normalized.columns:
        normalized["payment_id"] = [f"pay_{idx + 1}" for idx in range(len(normalized))]
        report["warnings"].append("payment_id was missing. Temporary IDs were assigned so the batch can still run. Review the mapping.")
    if "order_id" not in normalized.columns:
        normalized["order_id"] = [f"order_{idx + 1}" for idx in range(len(normalized))]

    money_cols = ["amount", "fee", "tax", "refund_amount", "settlement_amount", "adjustment"]
    for col in money_cols:
        if col in normalized.columns:
            before = normalized[col].copy()
            normalized[col] = pd.to_numeric(normalized[col], errors="coerce")
            bad = normalized[col].isna() & before.notna() & (before.astype(str).str.strip() != "")
            for idx in normalized.index[bad]:
                report["malformed_rows"].append({
                    "row": int(idx) + 2,
                    "field": col,
                    "value": str(before.loc[idx]),
                    "issue": "not a number",
                })

    if "amount" not in normalized.columns:
        normalized["amount"] = 0
        report["warnings"].append("amount was missing. Rows were loaded as 0 and flagged.")

    if _amounts_look_like_rupees(normalized["amount"]):
        report["units"] = "rupees_converted_to_paise"
        for col in money_cols:
            if col in normalized.columns:
                normalized[col] = (normalized[col] * 100).round()

    normalized["amount"] = pd.to_numeric(normalized["amount"], errors="coerce").fillna(0)

    if "fee" in normalized.columns:
        normalized["fee"] = pd.to_numeric(normalized["fee"], errors="coerce")
        missing_fee = normalized["fee"].isna()
        if missing_fee.any():
            report["warnings"].append(f"{int(missing_fee.sum())} rows had no fee; expected {FEE_PCT:.0%} of GMV was filled in.")
            normalized.loc[missing_fee, "fee"] = (normalized.loc[missing_fee, "amount"] * FEE_PCT).round()
    else:
        normalized["fee"] = (normalized["amount"] * FEE_PCT).round()
        report["warnings"].append(f"fee column missing; filled with {FEE_PCT:.0%} of amount.")

    if "tax" in normalized.columns:
        normalized["tax"] = pd.to_numeric(normalized["tax"], errors="coerce")
        missing_tax = normalized["tax"].isna()
        if missing_tax.any():
            report["warnings"].append(f"{int(missing_tax.sum())} rows had no tax; expected {TAX_PCT:.0%} of fee was filled in.")
            normalized.loc[missing_tax, "tax"] = (normalized.loc[missing_tax, "fee"] * TAX_PCT).round()
    else:
        normalized["tax"] = (normalized["fee"] * TAX_PCT).round()
        report["warnings"].append(f"tax column missing; filled with {TAX_PCT:.0%} of fee.")

    if "refund_amount" in normalized.columns:
        normalized["refund_amount"] = pd.to_numeric(normalized["refund_amount"], errors="coerce").fillna(0)
    else:
        normalized["refund_amount"] = 0
    if "adjustment" in normalized.columns:
        normalized["adjustment"] = pd.to_numeric(normalized["adjustment"], errors="coerce").fillna(0)
    else:
        normalized["adjustment"] = 0

    if "settlement_id" not in normalized.columns:
        normalized["settlement_id"] = pd.Series([None] * len(normalized), index=normalized.index)
    if "utr" not in normalized.columns:
        normalized["utr"] = normalized["settlement_id"]

    if "settlement_amount" in normalized.columns:
        normalized["settlement_amount"] = pd.to_numeric(normalized["settlement_amount"], errors="coerce")
    else:
        normalized["settlement_amount"] = pd.Series([pd.NA] * len(normalized), index=normalized.index)
        report["warnings"].append(
            "settlement_amount missing; left blank so missing bank credits stay exceptions instead of being invented."
        )

    normalized["status"] = normalized["status"].fillna("captured") if "status" in normalized.columns else "captured"
    normalized["payment_method"] = (
        normalized["payment_method"].fillna("upi") if "payment_method" in normalized.columns else "upi"
    )
    normalized["gstin"] = normalized["gstin"] if "gstin" in normalized.columns else "29AABCU9603R1ZX"
    normalized["source"] = normalized["source"].fillna("razorpay") if "source" in normalized.columns else "razorpay"
    normalized["currency"] = normalized["currency"].fillna("INR") if "currency" in normalized.columns else "INR"
    if "customer_id" not in normalized.columns:
        normalized["customer_id"] = [f"cust_{idx + 1}" for idx in range(len(normalized))]
    if "description" not in normalized.columns:
        normalized["description"] = ""

    if "created_at" not in normalized.columns or normalized["created_at"].isna().all():
        normalized["created_at"] = pd.to_datetime("2026-08-01")
        report["warnings"].append("created_at missing; defaulted to 2026-08-01.")
    else:
        parsed = pd.to_datetime(normalized["created_at"], errors="coerce")
        bad_dates = parsed.isna() & normalized["created_at"].notna()
        for idx in normalized.index[bad_dates]:
            report["malformed_rows"].append({
                "row": int(idx) + 2,
                "field": "created_at",
                "value": str(normalized.loc[idx, "created_at"]),
                "issue": "not a date",
            })
        normalized["created_at"] = parsed

    if "settled_at" not in normalized.columns or normalized["settled_at"].isna().all():
        normalized["settled_at"] = normalized["created_at"] + pd.Timedelta(days=2)
    else:
        normalized["settled_at"] = pd.to_datetime(normalized["settled_at"], errors="coerce")

    normalized["created_at"] = normalized["created_at"].fillna(pd.Timestamp("2026-08-01"))
    normalized["settled_at"] = normalized["settled_at"].fillna(normalized["created_at"] + pd.Timedelta(days=2))

    negative = normalized["amount"] < 0
    for idx in normalized.index[negative]:
        report["malformed_rows"].append({
            "row": int(idx) + 2,
            "field": "amount",
            "value": str(normalized.loc[idx, "amount"]),
            "issue": "negative amount",
        })

    preview_cols = [col for col in ["payment_id", "order_id", "amount", "fee", "tax", "settlement_id", "status"] if col in normalized.columns]
    report["preview"] = normalized[preview_cols].head(8).to_dict(orient="records")
    report["malformed_count"] = len(report["malformed_rows"])
    return normalized, report
