"""List payments and exceptions with backend date filters and totals."""

from __future__ import annotations

import pandas as pd

from serialize import json_safe, paise_to_rupees
from time_filters import apply_range, resolve_range


def _page(records: list, page: int, page_size: int) -> tuple[list, dict]:
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 25)))
    total = len(records)
    start = (page - 1) * page_size
    return records[start:start + page_size], {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size) if total else 1,
    }


def public_payment(row: dict, is_closed: bool = False) -> dict:
    status = row.get("reconciliation_status")
    return {
        "payment_id": json_safe(row.get("payment_id")),
        "order_id": json_safe(row.get("order_id")),
        "customer_id": json_safe(row.get("customer_id")),
        "amount": json_safe(row.get("amount")),
        "amount_rupees": paise_to_rupees(row.get("amount")),
        "currency": json_safe(row.get("currency")) or "INR",
        "status": json_safe(row.get("status")),
        "created_at": json_safe(row.get("created_at")),
        "settled_at": json_safe(row.get("settled_at")),
        "settlement_id": json_safe(row.get("settlement_id")),
        "settlement_amount": json_safe(row.get("settlement_amount")),
        "settlement_status": "settled" if row.get("settlement_id") not in (None, "") and pd.notna(row.get("settlement_amount")) else "missing",
        "reconciliation_status": json_safe(status),
        "mismatch_type": json_safe(row.get("mismatch_type")),
        "payment_method": json_safe(row.get("payment_method")),
        "fee": json_safe(row.get("fee")),
        "tax": json_safe(row.get("tax")),
        "refund_amount": json_safe(row.get("refund_amount")),
        "open_exception": bool(status == "exception" and not is_closed),
    }


def list_payments(reconciled: pd.DataFrame, is_closed, preset="all", start=None, end=None, start_time=None, end_time=None, q="", page=1, page_size=25, status="all"):
    bounds = resolve_range(preset, start, end, start_time, end_time)
    frame = apply_range(reconciled, "created_at", bounds) if reconciled is not None else pd.DataFrame()
    if not frame.empty and "created_at" in frame.columns:
        frame = frame.assign(_created=pd.to_datetime(frame["created_at"], errors="coerce"))
        frame = frame.sort_values("_created", ascending=False, na_position="last").drop(columns=["_created"])
    status = (status or "all").strip().lower()
    if q:
        needle = str(q).lower()
        keep = []
        for _, row in frame.iterrows():
            hay = " ".join(str(row.get(col) or "") for col in ("payment_id", "order_id", "status", "reconciliation_status", "mismatch_type"))
            if needle in hay.lower():
                keep.append(row.name)
        frame = frame.loc[keep] if keep else frame.iloc[0:0]

    all_records = [public_payment(row.to_dict(), is_closed(row["payment_id"])) for _, row in frame.iterrows()]
    matched = sum(1 for item in all_records if item["reconciliation_status"] == "matched")
    exceptions = sum(1 for item in all_records if item["reconciliation_status"] == "exception")
    gmv = paise_to_rupees(frame["amount"].sum()) if not frame.empty else 0.0
    at_risk = paise_to_rupees(
        frame.loc[frame["reconciliation_status"] == "exception", "amount"].sum()
    ) if not frame.empty and "reconciliation_status" in frame.columns else 0.0
    records = all_records
    if status in {"matched", "exception"}:
        records = [item for item in all_records if item["reconciliation_status"] == status]
    paged, meta = _page(records, page, page_size)
    return {
        "filter": {key: bounds[key] for key in ("preset", "start", "end", "warning") if key in bounds},
        "status": status if status in {"matched", "exception"} else "all",
        "totals": {
            "count": len(all_records),
            "matched": matched,
            "exceptions": exceptions,
            "gmv_rupees": gmv,
            "amount_at_risk_rupees": at_risk,
            "shown": len(records),
        },
        "records": paged,
        **meta,
    }


def search_exceptions(exceptions: list[dict], preset="all", start=None, end=None, start_time=None, end_time=None, q="", mismatch_type="all", page=1, page_size=25):
    bounds = resolve_range(preset, start, end, start_time, end_time)
    if bounds.get("inverted"):
        filtered = []
    else:
        filtered = []
        start_dt = bounds.get("start_dt")
        end_dt = bounds.get("end_dt")
        for item in exceptions:
            stamp = pd.to_datetime(item.get("created_at"), errors="coerce")
            if pd.isna(stamp):
                if start_dt or end_dt:
                    continue
            else:
                ts = stamp.to_pydatetime()
                if getattr(ts, "tzinfo", None):
                    ts = ts.replace(tzinfo=None)
                if start_dt and ts < start_dt:
                    continue
                if end_dt and ts > end_dt:
                    continue
            if mismatch_type and mismatch_type != "all" and item.get("mismatch_type") != mismatch_type:
                continue
            if q:
                hay = " ".join(str(item.get(key) or "") for key in ("payment_id", "exception_id", "mismatch_type", "explanation", "priority", "workflow_status"))
                if str(q).lower() not in hay.lower():
                    continue
            filtered.append(item)

    def _stamp(item):
        parsed = pd.to_datetime(item.get("created_at"), errors="coerce")
        return parsed.value if not pd.isna(parsed) else 0

    filtered.sort(key=_stamp, reverse=True)

    amount = sum(float(item.get("amount") or 0) for item in filtered)
    paged, meta = _page(filtered, page, page_size)
    return {
        "filter": {key: bounds[key] for key in ("preset", "start", "end", "warning")},
        "totals": {
            "count": len(filtered),
            "amount_rupees": paise_to_rupees(amount),
            "critical": sum(1 for item in filtered if item.get("priority") == "Critical"),
            "high": sum(1 for item in filtered if item.get("priority") == "High"),
        },
        "records": paged,
        **meta,
    }
