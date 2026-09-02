"""
Deterministic Finance Controller intelligence.

All money math lives here or in cash / reconciliation / ledgers.
The LLM may only describe these payloads — it never invents the numbers.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd

from config import CRITICAL_AMOUNT_PAISE, FEE_PCT, MAX_SETTLEMENT_DAYS, TAX_PCT, TOLERANCE_PAISE
from serialize import format_inr_compact, json_safe, paise_to_rupees


SLA_HOURS = 48
HIGH_VALUE_PAISE = max(CRITICAL_AMOUNT_PAISE, 500000)
ANOMALY_Z = 2.0
MIN_HISTORY_DAYS = 3


def _num(frame_or_row, key, default=0.0) -> float:
    if isinstance(frame_or_row, pd.DataFrame):
        return float(pd.to_numeric(frame_or_row[key], errors="coerce").fillna(default).sum()) if key in frame_or_row.columns else default
    value = frame_or_row.get(key, default) if hasattr(frame_or_row, "get") else default
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_ts(value) -> pd.Timestamp | None:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.tz_localize(None)
    return pd.Timestamp(ts)


def _pct_change(current, previous) -> float | None:
    current = float(current or 0)
    previous = float(previous or 0)
    if previous == 0:
        if current == 0:
            return 0.0
        return None
    return round((current - previous) / abs(previous) * 100.0, 2)


def _amount_band(paise: float) -> str:
    rupees = abs(paise) / 100.0
    if rupees < 1000:
        return "lt_1k"
    if rupees < 10000:
        return "1k_10k"
    if rupees < 50000:
        return "10k_50k"
    return "50k_plus"


def _ratio_bucket(numerator: float, denominator: float, places: int = 3) -> str:
    if not denominator:
        return "na"
    return f"{round(numerator / denominator, places):.{places}f}"


def empty_frame_metrics() -> dict:
    return {
        "payments": 0,
        "gmv_rupees": 0.0,
        "matched": 0,
        "exceptions": 0,
        "match_rate": 0.0,
        "exception_value_rupees": 0.0,
        "refund_count": 0,
        "refund_rupees": 0.0,
        "gst_issues": 0,
        "gst_delta_rupees": 0.0,
        "settlement_delay_count": 0,
        "unresolved_rupees": 0.0,
        "high_priority": 0,
        "withdrawals_rupees": 0.0,
        "available_cash_rupees": 0.0,
    }


def slice_by_created(df: pd.DataFrame, start, end) -> pd.DataFrame:
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    created = pd.to_datetime(df["created_at"], errors="coerce")
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return df[(created >= start_ts) & (created < end_ts)].copy()


def metrics_from_frame(
    df: pd.DataFrame,
    resolutions: dict | None = None,
    withdrawn_rupees: float = 0.0,
    available_cash_rupees: float | None = None,
) -> dict:
    if df is None or df.empty:
        payload = empty_frame_metrics()
        payload["withdrawals_rupees"] = round(float(withdrawn_rupees or 0), 2)
        payload["available_cash_rupees"] = round(float(available_cash_rupees or 0), 2)
        return payload

    total = int(len(df))
    matched = int((df["reconciliation_status"] == "matched").sum()) if "reconciliation_status" in df.columns else 0
    exceptions = df[df["reconciliation_status"] == "exception"] if "reconciliation_status" in df.columns else df.iloc[0:0]
    open_exceptions = exceptions
    if resolutions:
        open_ids = [
            pid for pid in exceptions["payment_id"].tolist()
            if not ((resolutions.get(pid) or {}).get("status") in {"resolved", "waived"})
        ]
        open_exceptions = exceptions[exceptions["payment_id"].isin(open_ids)]

    refund_mask = pd.to_numeric(df.get("refund_amount"), errors="coerce").fillna(0) > 0
    gst_issues = 0
    gst_delta = 0.0
    if "fee" in df.columns and "tax" in df.columns:
        expected_tax = pd.to_numeric(df["fee"], errors="coerce").fillna(0) * TAX_PCT
        actual_tax = pd.to_numeric(df["tax"], errors="coerce").fillna(0)
        gst_delta = float((actual_tax - expected_tax).abs().sum())
        gst_issues = int((actual_tax - expected_tax).abs().gt(TOLERANCE_PAISE).sum())

    delay_count = 0
    if "created_at" in df.columns and "settled_at" in df.columns:
        created = pd.to_datetime(df["created_at"], errors="coerce")
        settled = pd.to_datetime(df["settled_at"], errors="coerce")
        delay_count = int(((settled - created).dt.days > MAX_SETTLEMENT_DAYS).fillna(False).sum())

    high = 0
    if "priority" in open_exceptions.columns:
        high = int(open_exceptions["priority"].isin(["High", "Critical"]).sum())

    gmv = _num(df, "amount")
    unresolved = _num(open_exceptions, "amount")
    return {
        "payments": total,
        "gmv_rupees": paise_to_rupees(gmv),
        "matched": matched,
        "exceptions": int(len(open_exceptions)),
        "match_rate": round(matched / total, 4) if total else 0.0,
        "exception_value_rupees": paise_to_rupees(unresolved),
        "refund_count": int(refund_mask.sum()),
        "refund_rupees": paise_to_rupees(_num(df.loc[refund_mask] if refund_mask.any() else df.iloc[0:0], "refund_amount")),
        "gst_issues": gst_issues,
        "gst_delta_rupees": paise_to_rupees(gst_delta),
        "settlement_delay_count": delay_count,
        "unresolved_rupees": paise_to_rupees(unresolved),
        "high_priority": high,
        "withdrawals_rupees": round(float(withdrawn_rupees or 0), 2),
        "available_cash_rupees": round(float(available_cash_rupees or 0), 2),
    }


def snapshot_payload(batch_id, metrics: dict) -> dict:
    return {
        "batch_id": batch_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        **metrics,
    }


def greeting(as_of: datetime | None = None) -> str:
    hour = (as_of or datetime.now()).hour
    if hour < 12:
        return "Good morning."
    if hour < 17:
        return "Good afternoon."
    return "Good evening."


def briefing_text(numbers: dict, changes: list[dict], recurring: list[dict]) -> str:
    lines = [
        greeting(),
        f"{numbers['payments']} payments processed.",
        f"{format_inr_compact(numbers['gmv_rupees'])} processed.",
        f"{round(numbers['match_rate'] * 100, 1)}% reconciled.",
        f"{numbers['exceptions']} exceptions require attention.",
        f"{format_inr_compact(numbers['unresolved_rupees'])} remains unresolved.",
    ]
    if numbers.get("high_priority"):
        lines.append(f"{numbers['high_priority']} high-priority exceptions detected.")
    if numbers.get("pending_settlements_rupees"):
        lines.append(f"Pending settlements {format_inr_compact(numbers['pending_settlements_rupees'])}.")
    if numbers.get("refund_rupees"):
        lines.append(f"Refund exposure {format_inr_compact(numbers['refund_rupees'])}.")
    if numbers.get("gst_issues"):
        lines.append(f"{numbers['gst_issues']} GST/tax line issues.")
    if numbers.get("available_cash_rupees") is not None:
        lines.append(f"Cash available {format_inr_compact(numbers['available_cash_rupees'])}.")
    for item in changes[:3]:
        if item.get("headline"):
            lines.append(item["headline"])
    if recurring:
        top = recurring[0]
        lines.append(
            f"Recurring: {top.get('title') or top.get('mismatch_type')} affects "
            f"{top.get('count') or top.get('occurrences')} records "
            f"({format_inr_compact(top.get('impact_rupees') or top.get('affected_rupees') or 0)})."
        )
    return " ".join(lines)


def build_briefing(
    reconciled: pd.DataFrame,
    cash: dict | None,
    tax: dict | None,
    resolutions: dict | None,
    withdrawn_rupees: float,
    clusters: list[dict],
    changes: list[dict],
    aging_alerts: list[dict],
) -> dict:
    if reconciled is None or (hasattr(reconciled, "empty") and reconciled.empty):
        zeros = empty_frame_metrics()
        zeros.update({
            "pending_settlements_rupees": 0.0,
            "refund_exposure_rupees": 0.0,
            "gst_issues": 0,
            "cash_available_rupees": 0.0,
        })
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "numbers": zeros,
            "summary": "No reconciled batch is loaded. Load and run reconciliation to generate today's briefing.",
            "changes": [],
            "recurring": [],
            "aging_alerts": [],
            "ai_available": False,
        }

    numbers = metrics_from_frame(reconciled, resolutions, withdrawn_rupees, (cash or {}).get("available_rupees"))
    numbers["pending_settlements_rupees"] = float((cash or {}).get("in_transit_rupees") or 0)
    numbers["refund_exposure_rupees"] = numbers["refund_rupees"]
    numbers["gst_issues"] = int((tax or {}).get("mismatched_lines") or numbers["gst_issues"])
    numbers["cash_available_rupees"] = float((cash or {}).get("available_rupees") or 0)
    numbers["cash_blocked_rupees"] = float((cash or {}).get("blocked_rupees") or 0)
    payload_numbers = {
        **numbers,
        "pending_settlements_rupees": numbers["pending_settlements_rupees"],
        "available_cash_rupees": numbers["cash_available_rupees"],
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "numbers": payload_numbers,
        "summary": briefing_text(payload_numbers, changes, clusters),
        "changes": changes[:8],
        "recurring": clusters[:5],
        "aging_alerts": aging_alerts,
        "formula": "All figures are computed from the loaded reconciled batch, cash position, GST lines, and withdrawals.",
    }


def important_changes(current: dict, previous: dict, label: str) -> list[dict]:
    if not previous:
        return []
    specs = [
        ("payments", "Payments", False, 8),
        ("gmv_rupees", "Payment value", True, 8),
        ("match_rate", "Reconciliation rate", False, 1.5, True),
        ("exceptions", "Exception count", False, 0),
        ("exception_value_rupees", "Unresolved settlement value", True, 5),
        ("refund_rupees", "Refunds", True, 8),
        ("gst_issues", "GST issues", False, 0),
        ("settlement_delay_count", "Settlement delays", False, 0),
        ("withdrawals_rupees", "Withdrawals", True, 5),
        ("available_cash_rupees", "Available cash", True, 5),
        ("unresolved_rupees", "Unresolved amount", True, 5),
        ("high_priority", "High-priority exceptions", False, 0),
    ]
    out = []
    for spec in specs:
        key, title, money, threshold = spec[0], spec[1], spec[2], spec[3]
        rate = len(spec) > 4
        cur = float(current.get(key) or 0)
        prev = float(previous.get(key) or 0)
        pct = _pct_change(cur, prev)
        delta = cur - prev
        if rate:
            delta = round((cur - prev) * 100, 2)
            notable = abs(delta) >= threshold
            headline = f"{title} {'increased' if delta > 0 else 'decreased'} {abs(delta):.1f} pp vs {label}."
        elif money:
            notable = abs(delta) >= threshold or (pct is not None and abs(pct) >= threshold and abs(delta) >= 1)
            verb = "increased" if delta > 0 else "decreased"
            headline = f"{title} {verb} {format_inr_compact(abs(delta))} vs {label}."
            if pct is not None:
                headline = f"{title} {verb} {abs(pct):.0f}% vs {label}."
        else:
            notable = abs(delta) >= max(threshold, 1) or (pct is not None and abs(pct) >= 15 and abs(delta) >= 1)
            if delta == 0:
                continue
            verb = "increased" if delta > 0 else "decreased"
            if pct is None:
                headline = f"{title} {verb} by {abs(int(delta))} vs {label}."
            else:
                headline = f"{title} {verb} {abs(pct):.0f}% vs {label}."
        if not notable:
            continue
        out.append({
            "metric": key,
            "title": title,
            "current": cur,
            "previous": prev,
            "delta": round(delta, 4),
            "pct_change": pct,
            "headline": headline,
            "period": label,
        })
    out.sort(key=lambda item: abs(item.get("pct_change") or item["delta"]), reverse=True)
    return out[:10]


def compare_periods(
    reconciled: pd.DataFrame,
    resolutions: dict | None,
    withdrawn_rupees: float,
    available_cash_rupees: float,
    snapshots: list[dict],
    versus: str = "yesterday",
    as_of: datetime | None = None,
    current_batch_id: str | None = None,
) -> dict:
    as_of = as_of or datetime.now()
    today = pd.Timestamp(as_of).normalize()
    current_metrics = metrics_from_frame(reconciled, resolutions, withdrawn_rupees, available_cash_rupees)
    previous_metrics = empty_frame_metrics()
    label = versus
    note = None

    if versus == "yesterday":
        current = slice_by_created(reconciled, today, today + timedelta(days=1))
        previous = slice_by_created(reconciled, today - timedelta(days=1), today)
        current_metrics = metrics_from_frame(current, resolutions, 0.0, available_cash_rupees)
        previous_metrics = metrics_from_frame(previous, resolutions, 0.0, None)
        label = "yesterday"
        if previous.empty:
            note = "No payments dated yesterday. Comparison uses whatever rows exist in that window."
    elif versus in {"7d", "previous_7_days"}:
        current = slice_by_created(reconciled, today - timedelta(days=7), today + timedelta(days=1))
        previous = slice_by_created(reconciled, today - timedelta(days=14), today - timedelta(days=7))
        current_metrics = metrics_from_frame(current, resolutions, withdrawn_rupees, available_cash_rupees)
        previous_metrics = metrics_from_frame(previous, resolutions, 0.0, None)
        label = "the previous 7 days"
    elif versus in {"batch", "previous_batch"}:
        current_metrics = metrics_from_frame(reconciled, resolutions, withdrawn_rupees, available_cash_rupees)
        previous_metrics = _previous_batch_snapshot(snapshots, current_batch_id)
        label = "the previous batch"
        if not previous_metrics:
            previous_metrics = empty_frame_metrics()
            note = "No previous batch snapshot is stored yet."
    elif versus in {"comparable", "previous_comparable_period"}:
        current = slice_by_created(reconciled, today - timedelta(days=7), today + timedelta(days=1))
        previous = slice_by_created(reconciled, today - timedelta(days=14), today - timedelta(days=7))
        current_metrics = metrics_from_frame(current, resolutions, withdrawn_rupees, available_cash_rupees)
        previous_metrics = metrics_from_frame(previous, resolutions, 0.0, None)
        label = "the previous comparable week"
    else:
        note = f"Unknown comparison '{versus}'. Used yesterday."
        current = slice_by_created(reconciled, today, today + timedelta(days=1))
        previous = slice_by_created(reconciled, today - timedelta(days=1), today)
        current_metrics = metrics_from_frame(current, resolutions, 0.0, available_cash_rupees)
        previous_metrics = metrics_from_frame(previous, resolutions, 0.0, None)
        label = "yesterday"

    changes = important_changes(current_metrics, previous_metrics, label)
    return {
        "versus": versus,
        "label": label,
        "current": current_metrics,
        "previous": previous_metrics,
        "changes": changes,
        "note": note,
        "insufficient_history": bool(note) or (previous_metrics.get("payments", 0) == 0 and versus != "batch"),
    }


def _previous_batch_snapshot(snapshots: list[dict], current_batch_id) -> dict | None:
    for item in snapshots or []:
        if current_batch_id and item.get("batch_id") == current_batch_id:
            continue
        if item.get("batch_id"):
            return item
    if snapshots and len(snapshots) >= 2:
        return snapshots[1]
    return None


def _cluster_key(row) -> str:
    mismatch = str(row.get("mismatch_type") or "unclassified_discrepancy")
    method = str(row.get("payment_method") or "unknown").lower()
    amount = _num(row, "amount")
    fee = _num(row, "fee")
    tax = _num(row, "tax")
    refund = _num(row, "refund_amount")
    has_settlement = "yes" if row.get("settlement_id") not in (None, "", float("nan")) and not (isinstance(row.get("settlement_id"), float) and pd.isna(row.get("settlement_id"))) else "no"
    if mismatch == "fee_miscalculation":
        signature = f"fee:{_ratio_bucket(fee, amount)}"
    elif mismatch == "tax_line_mismatch":
        signature = f"tax:{_ratio_bucket(tax, fee if fee else amount)}"
    elif mismatch == "unaccounted_refund":
        signature = f"refund:{_ratio_bucket(refund, amount)}|{has_settlement}"
    elif mismatch == "missing_settlement":
        signature = f"missing|{method}"
    elif mismatch == "timing_mismatch":
        signature = f"timing|{method}"
    else:
        signature = f"{_amount_band(amount)}|{has_settlement}|{_ratio_bucket(fee, amount)}"
    return f"{mismatch}|{method}|{signature}"


def _root_cause_for_cluster(mismatch: str, rows: list[dict]) -> dict:
    fees = [_ratio_bucket(_num(r, "fee"), _num(r, "amount")) for r in rows]
    methods = {str(r.get("payment_method") or "unknown") for r in rows}
    gstins = {str(r.get("gstin") or "") for r in rows if r.get("gstin")}
    expected_fee_ratio = f"{FEE_PCT:.3f}"
    expected_tax_ratio = f"{TAX_PCT:.3f}"

    evidence = [
        f"{len(rows)} records share mismatch {mismatch.replace('_', ' ')}.",
        f"Payment methods: {', '.join(sorted(methods))}.",
    ]
    if gstins:
        evidence.append(f"GSTIN(s): {', '.join(sorted(gstins)[:4])}.")

    if mismatch == "fee_miscalculation" and len(set(fees)) == 1 and fees[0] != expected_fee_ratio:
        return {
            "status": "confirmed",
            "label": "Confirmed cause",
            "cause": "Shared fee configuration / fee rate on these payments does not match the configured GMV fee.",
            "confidence": 0.96,
            "evidence": evidence + [f"Every record has fee/GMV ratio {fees[0]} vs configured {expected_fee_ratio}."],
        }
    if mismatch == "tax_line_mismatch":
        tax_ratios = [_ratio_bucket(_num(r, "tax"), _num(r, "fee")) for r in rows]
        if len(set(tax_ratios)) == 1 and tax_ratios[0] != expected_tax_ratio:
            return {
                "status": "confirmed",
                "label": "Confirmed cause",
                "cause": "GST on fee is applied at a single incorrect rate across the cluster.",
                "confidence": 0.95,
                "evidence": evidence + [f"GST/fee ratio {tax_ratios[0]} vs configured {expected_tax_ratio}."],
            }
    if mismatch == "missing_settlement":
        missing = all(not r.get("settlement_id") or (isinstance(r.get("settlement_id"), float) and pd.isna(r.get("settlement_id"))) for r in rows)
        if missing:
            return {
                "status": "confirmed",
                "label": "Confirmed cause",
                "cause": "No settlement identifier is present on these payments. A bank credit cannot be invented.",
                "confidence": 0.99,
                "evidence": evidence + ["settlement_id is absent on every member."],
            }
    if mismatch == "timing_mismatch":
        return {
            "status": "probable",
            "label": "Probable cause",
            "cause": "Amounts can still match; settlement landed outside the expected window.",
            "confidence": 0.82,
            "evidence": evidence,
        }
    if len(rows) >= 3 and len(methods) == 1:
        return {
            "status": "probable",
            "label": "Probable cause",
            "cause": f"Repeated {mismatch.replace('_', ' ')} on {next(iter(methods))} with a shared amount/fee pattern.",
            "confidence": 0.78,
            "evidence": evidence + ["Pattern is strong but not every arithmetic field is identical."],
        }
    return {
        "status": "unknown",
        "label": "Unknown",
        "cause": "Insufficient evidence to confirm a single root cause. Human investigation recommended.",
        "confidence": 0.4,
        "evidence": evidence,
    }


def cluster_exceptions(reconciled: pd.DataFrame, resolutions: dict | None = None) -> list[dict]:
    if reconciled is None or reconciled.empty:
        return []
    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"].copy()
    if exceptions.empty:
        return []
    if resolutions:
        keep = [
            pid for pid in exceptions["payment_id"].tolist()
            if not ((resolutions.get(pid) or {}).get("status") in {"resolved", "waived"})
        ]
        exceptions = exceptions[exceptions["payment_id"].isin(keep)]
    buckets: dict[str, list[dict]] = defaultdict(list)
    for _, row in exceptions.iterrows():
        payload = row.to_dict()
        buckets[_cluster_key(payload)].append(payload)

    clusters = []
    for key, rows in buckets.items():
        if len(rows) < 2:
            continue
        mismatch = str(rows[0].get("mismatch_type") or "unclassified_discrepancy")
        impact = sum(_num(r, "amount") for r in rows)
        created = [_as_ts(r.get("created_at")) for r in rows]
        created = [ts for ts in created if ts is not None]
        root = _root_cause_for_cluster(mismatch, rows)
        cluster_id = "cl_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
        methods = sorted({str(r.get("payment_method") or "unknown") for r in rows})
        merchants = sorted({str(r.get("customer_id") or r.get("gstin") or "") for r in rows if r.get("customer_id") or r.get("gstin")})
        suggested = "apply_fix" if mismatch in {"fee_miscalculation", "tax_line_mismatch", "unaccounted_refund", "duplicate_record", "timing_mismatch"} else "escalate"
        clusters.append({
            "cluster_id": cluster_id,
            "key": key,
            "title": f"Recurring {mismatch.replace('_', ' ')}",
            "mismatch_type": mismatch,
            "count": len(rows),
            "impact_rupees": paise_to_rupees(impact),
            "payment_methods": methods,
            "merchants": merchants[:8],
            "first_occurrence": min(created).isoformat() if created else None,
            "latest_occurrence": max(created).isoformat() if created else None,
            "payment_ids": list(dict.fromkeys(r["payment_id"] for r in rows)),
            "root_cause": root,
            "recommended_action": (
                f"Review {len(rows)} records, then resolve as a group."
                if suggested == "apply_fix"
                else "Escalate — this type cannot be auto-fixed without inventing a credit."
            ),
            "auto_fixable": suggested == "apply_fix",
            "suggested_action": suggested,
        })
    clusters.sort(key=lambda item: (item["impact_rupees"], item["count"]), reverse=True)
    return clusters


def cash_gap(reconciled: pd.DataFrame, cash: dict | None, withdrawn_rupees: float = 0.0) -> dict:
    if reconciled is None or reconciled.empty:
        return {
            "expected_rupees": 0.0,
            "actual_rupees": 0.0,
            "difference_rupees": 0.0,
            "breakdown": [],
            "unexplained_rupees": 0.0,
            "fully_explained": True,
            "summary": "No reconciled batch is loaded.",
        }

    gmv = _num(reconciled, "amount")
    fees = _num(reconciled, "fee")
    tax = _num(reconciled, "tax")
    refunds = _num(reconciled, "refund_amount")
    expected = paise_to_rupees(gmv)
    actual = float((cash or {}).get("available_rupees") or 0)
    difference = round(expected - actual, 2)
    pending = float((cash or {}).get("in_transit_rupees") or 0)
    blocked = float((cash or {}).get("blocked_rupees") or 0)
    withdrawn = float(withdrawn_rupees or (cash or {}).get("withdrawn_rupees") or 0)
    breakdown = [
        {"id": "pending_settlements", "label": "Pending settlements", "rupees": round(pending, 2)},
        {"id": "refunds", "label": "Refunds", "rupees": paise_to_rupees(refunds)},
        {"id": "fees", "label": "Fees", "rupees": paise_to_rupees(fees)},
        {"id": "gst", "label": "GST", "rupees": paise_to_rupees(tax)},
        {"id": "unresolved", "label": "Unresolved exceptions", "rupees": round(blocked, 2)},
        {"id": "withdrawals", "label": "Withdrawals", "rupees": round(withdrawn, 2)},
    ]
    accounted = round(sum(item["rupees"] for item in breakdown) + actual, 2)
    unexplained = round(expected - accounted, 2)
    fully = abs(unexplained) <= paise_to_rupees(TOLERANCE_PAISE)
    if fully:
        summary = (
            f"The current cash position is {format_inr_compact(difference)} below expected GMV. "
            "The difference is accounted for by pending settlements, refunds, fees, GST, unresolved exceptions and withdrawals."
        )
    else:
        summary = (
            f"{format_inr_compact(abs(unexplained))} remains unexplained. Human investigation recommended."
        )
    return {
        "expected_rupees": expected,
        "actual_rupees": actual,
        "difference_rupees": difference,
        "breakdown": breakdown,
        "accounted_rupees": accounted,
        "unexplained_rupees": unexplained,
        "fully_explained": fully,
        "summary": summary,
        "formula": "expected = sum(amount); actual = available cash after withdrawals; unexplained = expected − (actual + pending + refunds + fees + GST + unresolved + withdrawals).",
    }


def parse_search_query(question: str) -> dict:
    q = (question or "").strip()
    lowered = q.lower()
    filters: dict = {"raw": q, "kind": "all"}
    pid = re.search(r"\b(pay_[a-z0-9]+)\b", lowered)
    if pid:
        filters["payment_id"] = pid.group(1)
    oid = re.search(r"\b(order_[a-z0-9]+)\b", lowered)
    if oid:
        filters["order_id"] = oid.group(1)
    wid = re.search(r"\b(wd_[a-z0-9]+)\b", lowered)
    if wid:
        filters["withdrawal_id"] = wid.group(1)

    if any(term in lowered for term in ("refund", "refunds")):
        filters["kind"] = "refund"
    elif any(term in lowered for term in ("withdrawal", "withdrawals", "payout")):
        filters["kind"] = "withdrawal"
    elif any(term in lowered for term in ("gst", "tax")):
        filters["kind"] = "gst"
    elif "audit" in lowered:
        filters["kind"] = "audit"
    elif any(term in lowered for term in ("settlement", "settlements")):
        filters["kind"] = "settlement"
    elif any(term in lowered for term in ("exception", "unresolved", "discrepancy", "mismatch")):
        filters["kind"] = "exception"
    elif "payment" in lowered or filters.get("payment_id"):
        filters["kind"] = "payment"

    amount = re.search(r"(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakh|lac|l)?", lowered)
    if amount and any(term in lowered for term in ("above", "greater", "over", ">", "at least")):
        value = float(amount.group(1).replace(",", ""))
        if amount.group(2):
            value *= 100000
        filters["min_rupees"] = value

    now = datetime.now()
    if "yesterday" in lowered:
        start = datetime(now.year, now.month, now.day) - timedelta(days=1)
        filters["start"] = start.isoformat()
        filters["end"] = (start + timedelta(days=1)).isoformat()
    elif "last week" in lowered or "past week" in lowered:
        start = datetime.now() - timedelta(days=7)
        filters["start"] = start.isoformat()
        filters["end"] = datetime.now().isoformat()
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for name, month in months.items():
        if name in lowered:
            year = now.year
            start = datetime(year, month, 1)
            if month == 12:
                end = datetime(year + 1, 1, 1)
            else:
                end = datetime(year, month + 1, 1)
            filters["start"] = start.isoformat()
            filters["end"] = end.isoformat()
            break
    merchant = re.search(r"merchant\s+([a-z0-9_\-]+)", lowered)
    if merchant:
        filters["merchant"] = merchant.group(1)
    return filters


def _in_range(value, start, end) -> bool:
    if not start and not end:
        return True
    ts = _as_ts(value)
    if ts is None:
        return False
    if start and ts < pd.Timestamp(start):
        return False
    if end and ts >= pd.Timestamp(end):
        return False
    return True


def search_finance(
    reconciled: pd.DataFrame,
    question: str,
    tax: dict | None = None,
    withdrawals: list | None = None,
    audit: list | None = None,
    resolutions: dict | None = None,
) -> dict:
    filters = parse_search_query(question)
    kind = filters.get("kind") or "all"
    results = {"payments": [], "exceptions": [], "refunds": [], "settlements": [], "gst": [], "withdrawals": [], "audit": [], "customers": []}
    if reconciled is None or reconciled.empty:
        return {"filters": filters, "results": results, "total": 0, "note": "No reconciled batch is loaded."}

    frame = reconciled.copy()
    if filters.get("payment_id"):
        frame = frame[frame["payment_id"].astype(str).str.lower() == filters["payment_id"].lower()]
    if filters.get("order_id") and "order_id" in frame.columns:
        frame = frame[frame["order_id"].astype(str).str.lower() == filters["order_id"].lower()]
    if filters.get("merchant"):
        key = filters["merchant"].lower()
        mask = False
        for col in ("customer_id", "gstin"):
            if col in frame.columns:
                mask = mask | frame[col].astype(str).str.lower().str.contains(key, na=False)
        frame = frame[mask] if isinstance(mask, pd.Series) else frame.iloc[0:0]
    if filters.get("min_rupees"):
        frame = frame[pd.to_numeric(frame["amount"], errors="coerce").fillna(0) >= filters["min_rupees"] * 100]
    if filters.get("start") or filters.get("end"):
        created = pd.to_datetime(frame["created_at"], errors="coerce")
        if filters.get("start"):
            frame = frame[created >= pd.Timestamp(filters["start"])]
            created = pd.to_datetime(frame["created_at"], errors="coerce")
        if filters.get("end"):
            frame = frame[created < pd.Timestamp(filters["end"])]

    def slim(rows, extra=None):
        cols = ["payment_id", "order_id", "amount", "refund_amount", "settlement_amount", "reconciliation_status", "mismatch_type", "status", "created_at", "customer_id", "priority"]
        extra = extra or []
        use = [c for c in cols + extra if c in rows.columns]
        return [{k: json_safe(rec[k]) for k in use} for rec in rows[use].head(25).to_dict(orient="records")]

    results["payments"] = slim(frame)
    exceptions = frame[frame["reconciliation_status"] == "exception"] if "reconciliation_status" in frame.columns else frame.iloc[0:0]
    results["exceptions"] = slim(exceptions)
    refunds = frame[pd.to_numeric(frame.get("refund_amount"), errors="coerce").fillna(0) > 0]
    results["refunds"] = slim(refunds)
    if "settlement_amount" in frame.columns:
        settled = frame[pd.to_numeric(frame["settlement_amount"], errors="coerce").notna()]
        results["settlements"] = slim(settled)
    if kind == "gst" and tax:
        lines = tax.get("lines") or []
        min_r = filters.get("min_rupees")
        results["gst"] = [
            line for line in lines
            if (not min_r or abs(float(line.get("delta_rupees") or 0)) >= min_r or float(line.get("actual_gst_rupees") or 0) >= min_r)
        ][:25]
    if kind in {"withdrawal", "all"} and withdrawals:
        results["withdrawals"] = withdrawals[:25]
    if kind in {"audit", "all"} and audit:
        results["audit"] = audit[:25]
    if "customer_id" in frame.columns:
        grouped = frame.groupby(frame["customer_id"].astype(str))
        customers = []
        for cid, group in grouped:
            if cid in {"nan", "None", ""}:
                continue
            customers.append({
                "customer_id": cid,
                "payments": int(len(group)),
                "gmv_rupees": paise_to_rupees(_num(group, "amount")),
                "exceptions": int((group["reconciliation_status"] == "exception").sum()) if "reconciliation_status" in group.columns else 0,
            })
        customers.sort(key=lambda item: item["gmv_rupees"], reverse=True)
        results["customers"] = customers[:12]

    focused = kind if kind != "all" else None
    mapping = {
        "payment": "payments",
        "exception": "exceptions",
        "refund": "refunds",
        "settlement": "settlements",
        "gst": "gst",
        "withdrawal": "withdrawals",
        "audit": "audit",
    }
    if focused and mapping.get(focused):
        primary = results[mapping[focused]]
    else:
        primary = results["payments"]
    total = sum(len(v) for v in results.values())
    return {"filters": filters, "results": results, "primary": primary, "total": total}


def exception_aging(reconciled: pd.DataFrame, resolutions: dict | None = None, sla_hours: int = SLA_HOURS) -> dict:
    if reconciled is None or reconciled.empty:
        return {"items": [], "alerts": [], "sla_hours": sla_hours}
    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"]
    now = pd.Timestamp(datetime.now())
    items = []
    aged_high = []
    for _, row in exceptions.iterrows():
        pid = row["payment_id"]
        if resolutions and (resolutions.get(pid) or {}).get("status") in {"resolved", "waived"}:
            continue
        created = _as_ts(row.get("created_at")) or now
        age_hours = max(0.0, (now - created).total_seconds() / 3600.0)
        last_activity = created
        resolution = (resolutions or {}).get(pid) or {}
        if resolution.get("at"):
            last_activity = _as_ts(resolution["at"]) or last_activity
        exposure = _num(row, "amount")
        item = {
            "payment_id": pid,
            "mismatch_type": json_safe(row.get("mismatch_type")),
            "priority": row.get("priority") or "Low",
            "created_at": created.isoformat(),
            "last_activity": last_activity.isoformat() if last_activity is not None else None,
            "age_hours": round(age_hours, 2),
            "status": resolution.get("workflow_status") or "Unreviewed",
            "exposure_rupees": paise_to_rupees(exposure),
            "score": round(age_hours / 24.0 * paise_to_rupees(exposure) / 1000.0, 4),
        }
        items.append(item)
        if age_hours >= sla_hours and (item["priority"] in {"High", "Critical"} or exposure >= HIGH_VALUE_PAISE):
            aged_high.append(item)
    items.sort(key=lambda item: (item["score"], item["age_hours"]), reverse=True)
    alerts = []
    if aged_high:
        alerts.append({
            "severity": "high",
            "message": f"{len(aged_high)} high-value exceptions have remained unresolved for more than {sla_hours} hours.",
            "payment_ids": [item["payment_id"] for item in aged_high[:12]],
        })
    return {"items": items[:100], "alerts": alerts, "sla_hours": sla_hours, "breached": len(aged_high)}


def detect_anomalies(reconciled: pd.DataFrame, as_of: datetime | None = None) -> dict:
    if reconciled is None or reconciled.empty:
        return {"signals": [], "note": "No data loaded.", "insufficient_history": True}
    as_of = as_of or datetime.now()
    df = reconciled.copy()
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df[df["created_at"].notna()]
    if df.empty:
        return {"signals": [], "note": "created_at missing; cannot build a daily baseline.", "insufficient_history": True}
    df["day"] = df["created_at"].dt.normalize()
    daily = df.groupby("day").agg(
        payments=("payment_id", "count"),
        gmv=("amount", lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum()),
        refunds=("refund_amount", lambda s: pd.to_numeric(s, errors="coerce").fillna(0).sum()),
    )
    if len(daily) < MIN_HISTORY_DAYS:
        return {
            "signals": [],
            "note": f"Insufficient historical data ({len(daily)} day(s)). Need at least {MIN_HISTORY_DAYS} distinct days.",
            "insufficient_history": True,
            "days": int(len(daily)),
        }
    today = pd.Timestamp(as_of).normalize()
    if today not in daily.index:
        latest = daily.index.max()
        today_row = daily.loc[latest]
        baseline = daily.drop(index=latest)
        day_label = str(latest.date())
    else:
        today_row = daily.loc[today]
        baseline = daily.drop(index=today)
        day_label = str(today.date())
    if baseline.empty:
        return {"signals": [], "note": "Insufficient historical data after removing today.", "insufficient_history": True}

    signals = []
    for field, label in (("payments", "payment volume"), ("gmv", "payment value"), ("refunds", "refund value")):
        series = baseline[field].astype(float)
        mean = float(series.mean())
        std = float(series.std(ddof=0)) or 0.0
        current = float(today_row[field])
        if std == 0:
            continue
        z = (current - mean) / std
        if abs(z) >= ANOMALY_Z:
            pct = _pct_change(current, mean)
            signals.append({
                "id": field,
                "label": label,
                "day": day_label,
                "current": paise_to_rupees(current) if field != "payments" else current,
                "baseline_mean": paise_to_rupees(mean) if field != "payments" else round(mean, 2),
                "z_score": round(z, 2),
                "pct_vs_mean": pct,
                "message": (
                    f"Unusual {label} detected. {day_label} is {abs(pct or 0):.0f}% "
                    f"{'above' if (pct or 0) > 0 else 'below'} the normal range for this day."
                ),
                "terminology": "anomaly",
            })
    duplicate_like = 0
    if "amount" in df.columns:
        grouped = df.groupby(["customer_id", "amount"]) if "customer_id" in df.columns else None
        if grouped is not None:
            duplicate_like = int((grouped["payment_id"].count() >= 3).sum())
            if duplicate_like:
                signals.append({
                    "id": "repeat_amounts",
                    "label": "repeated duplicate-like transactions",
                    "message": f"{duplicate_like} customer/amount pairs repeat 3+ times. Requires review — not claimed as fraud.",
                    "terminology": "suspicious signal",
                })
    return {
        "signals": signals,
        "insufficient_history": False,
        "baseline_days": int(len(baseline)),
        "note": None if signals else "No unusual pattern versus the daily baseline.",
    }


def refund_intelligence(reconciled: pd.DataFrame, as_of: datetime | None = None) -> dict:
    if reconciled is None or reconciled.empty:
        return {
            "pending_count": 0, "completed_count": 0, "refund_rupees": 0.0, "refund_rate": 0.0,
            "trend_pct": None, "exceptions": 0, "note": "No data loaded.",
        }
    as_of = as_of or datetime.now()
    today = pd.Timestamp(as_of).normalize()
    refunds = pd.to_numeric(reconciled.get("refund_amount"), errors="coerce").fillna(0)
    status = reconciled.get("status")
    pending = 0
    completed = int((refunds > 0).sum())
    if status is not None:
        pending = int(status.astype(str).str.contains("refund", case=False, na=False).sum())
        # completed = captured refunds already applied
        completed = int((refunds > 0).sum())
    gmv = _num(reconciled, "amount")
    refund_paise = float(refunds.sum())
    last7 = slice_by_created(reconciled, today - timedelta(days=7), today + timedelta(days=1))
    prev7 = slice_by_created(reconciled, today - timedelta(days=14), today - timedelta(days=7))
    last7_amt = _num(last7, "refund_amount")
    prev7_amt = _num(prev7, "refund_amount")
    trend = _pct_change(last7_amt, prev7_amt / 7 * 7 if prev7_amt else prev7_amt)
    exceptions = 0
    if "mismatch_type" in reconciled.columns:
        exceptions = int(((reconciled["reconciliation_status"] == "exception") & (reconciled["mismatch_type"] == "unaccounted_refund")).sum())
    spike = trend is not None and trend >= 20
    return {
        "pending_count": pending,
        "completed_count": completed,
        "refund_rupees": paise_to_rupees(refund_paise),
        "refund_rate": round(refund_paise / gmv, 4) if gmv else 0.0,
        "trend_pct": trend,
        "last_7d_rupees": paise_to_rupees(last7_amt),
        "prev_7d_avg_rupees": paise_to_rupees(prev7_amt),
        "exceptions": exceptions,
        "spike": spike,
        "message": (
            f"Refund volume increased {trend:.0f}% compared with the previous 7-day total."
            if spike and trend is not None else
            "Refund volume is within the recent 7-day range." if trend is not None else
            "Not enough history to compute a refund trend."
        ),
        "sample_ids": reconciled.loc[refunds > 0, "payment_id"].astype(str).head(12).tolist() if (refunds > 0).any() else [],
    }


def action_queue(
    reconciled: pd.DataFrame,
    clusters: list[dict],
    cash: dict | None,
    tax: dict | None,
    aging: dict | None,
    anomalies: dict | None,
    refunds: dict | None,
    resolutions: dict | None = None,
) -> list[dict]:
    queue = []
    if reconciled is None or (hasattr(reconciled, "empty") and reconciled.empty):
        return queue

    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"]
    open_rows = []
    for _, row in exceptions.iterrows():
        pid = row["payment_id"]
        if resolutions and (resolutions.get(pid) or {}).get("status") in {"resolved", "waived"}:
            continue
        open_rows.append(row.to_dict())

    missing = [r for r in open_rows if r.get("mismatch_type") == "missing_settlement"]
    if missing:
        impact = paise_to_rupees(sum(_num(r, "amount") for r in missing))
        top = max(missing, key=lambda r: _num(r, "amount"))
        queue.append({
            "id": "missing_settlement",
            "priority": "critical" if impact >= 50000 else "high",
            "title": f"Resolve {format_inr_compact(impact)} missing settlement",
            "reason": f"{len(missing)} payments have no settlement_id. The engine will not invent a UTR.",
            "amount_rupees": impact,
            "age_hours": None,
            "confidence": 0.99,
            "related_records": [r["payment_id"] for r in missing[:8]],
            "next_step": "Open the exception queue and chase the bank / Razorpay credit.",
            "href": "exceptions",
            "focus_id": top["payment_id"],
        })

    for cluster in clusters[:4]:
        queue.append({
            "id": cluster["cluster_id"],
            "priority": "high" if cluster["impact_rupees"] >= 10000 else "medium",
            "title": f"Review recurring {cluster['mismatch_type'].replace('_', ' ')} ({cluster['count']} records)",
            "reason": cluster["root_cause"]["cause"],
            "amount_rupees": cluster["impact_rupees"],
            "confidence": cluster["root_cause"]["confidence"],
            "related_records": cluster["payment_ids"][:8],
            "next_step": cluster["recommended_action"],
            "href": "exceptions",
            "cluster_id": cluster["cluster_id"],
        })

    gst_n = int((tax or {}).get("mismatched_lines") or 0)
    if gst_n:
        queue.append({
            "id": "gst",
            "priority": "high" if gst_n >= 5 else "medium",
            "title": f"Review {gst_n} GST mismatches",
            "reason": "GST collected differs from 18% of fee on these lines.",
            "amount_rupees": float((tax or {}).get("delta_rupees") or 0),
            "confidence": 0.94,
            "related_records": [line.get("payment_id") for line in (tax or {}).get("lines", [])[:8]],
            "next_step": "Open GST and inspect mismatched tax lines.",
            "href": "gst",
        })

    auto = [r for r in open_rows if r.get("mismatch_type") in {"fee_miscalculation", "tax_line_mismatch", "unaccounted_refund", "duplicate_record", "timing_mismatch"}]
    if auto:
        queue.append({
            "id": "ai_recommendations",
            "priority": "medium",
            "title": f"Approve {len(auto)} arithmetic recommendations",
            "reason": "These types are auto-fixable after human confirmation.",
            "amount_rupees": paise_to_rupees(sum(_num(r, "amount") for r in auto)),
            "confidence": 0.9,
            "related_records": [r["payment_id"] for r in auto[:8]],
            "next_step": "Review evidence, then confirm batch resolution.",
            "href": "exceptions",
        })

    timing = [r for r in open_rows if r.get("mismatch_type") == "timing_mismatch"]
    if timing:
        queue.append({
            "id": "timing",
            "priority": "low",
            "title": f"Review {len(timing)} recurring timing discrepancies",
            "reason": "Amounts may match; only the settlement window was breached.",
            "amount_rupees": paise_to_rupees(sum(_num(r, "amount") for r in timing)),
            "confidence": 0.8,
            "related_records": [r["payment_id"] for r in timing[:8]],
            "next_step": "Waive after a human check, or leave open.",
            "href": "exceptions",
        })

    for alert in (aging or {}).get("alerts") or []:
        queue.append({
            "id": "aging",
            "priority": "critical",
            "title": alert["message"],
            "reason": f"SLA is {(aging or {}).get('sla_hours', SLA_HOURS)} hours for high-value open exceptions.",
            "amount_rupees": 0,
            "confidence": 1.0,
            "related_records": alert.get("payment_ids") or [],
            "next_step": "Prioritise these records in the exception queue.",
            "href": "exceptions",
        })

    if (refunds or {}).get("spike"):
        queue.append({
            "id": "refund_spike",
            "priority": "high",
            "title": "Investigate refund spike",
            "reason": refunds.get("message"),
            "amount_rupees": refunds.get("refund_rupees") or 0,
            "confidence": 0.7,
            "related_records": refunds.get("sample_ids") or [],
            "next_step": "Open refund intelligence and trace the underlying refund records.",
            "href": "payments",
        })

    for signal in (anomalies or {}).get("signals") or []:
        queue.append({
            "id": f"anomaly_{signal.get('id')}",
            "priority": "medium",
            "title": signal.get("message") or signal.get("label"),
            "reason": "Unusual versus the historical daily baseline. Not claimed as fraud.",
            "amount_rupees": 0,
            "confidence": min(0.9, abs(float(signal.get("z_score") or 2)) / 4),
            "related_records": [],
            "next_step": "Review payments for that day.",
            "href": "payments",
        })

    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    queue.sort(key=lambda item: (rank.get(item["priority"], 9), -(item.get("amount_rupees") or 0)))
    return queue[:16]


def health_score(
    metrics: dict,
    cash: dict | None,
    tax: dict | None,
    aging: dict | None,
    anomalies: dict | None,
    refunds: dict | None,
) -> dict:
    match_rate = float((metrics or {}).get("match_rate") or 0)
    unresolved = float((metrics or {}).get("unresolved_exceptions") or (metrics or {}).get("exceptions") or 0)
    at_risk = paise_to_rupees((metrics or {}).get("amount_at_risk") or 0)
    high = int(((metrics or {}).get("priority_breakdown") or {}).get("High") or 0) + int(((metrics or {}).get("priority_breakdown") or {}).get("Critical") or 0)
    gst_issues = int((tax or {}).get("mismatched_lines") or 0)
    aging_n = int((aging or {}).get("breached") or 0)
    refund_spike = 8 if (refunds or {}).get("spike") else 0
    anomaly_n = len((anomalies or {}).get("signals") or [])
    blocked = float((cash or {}).get("blocked_rupees") or 0)

    deductions = []
    recon_pen = round((1 - match_rate) * 30, 2)
    deductions.append({"reason": f"Reconciliation rate {round(match_rate * 100, 1)}%", "points": recon_pen})
    exposure_pen = min(25.0, at_risk / 100000.0 * 5)
    if exposure_pen:
        deductions.append({"reason": f"Unresolved exposure {format_inr_compact(at_risk)}", "points": round(exposure_pen, 2)})
    high_pen = min(15.0, high * 3)
    if high_pen:
        deductions.append({"reason": f"{high} high-priority exceptions", "points": round(high_pen, 2)})
    age_pen = min(10.0, aging_n * 4)
    if age_pen:
        deductions.append({"reason": f"{aging_n} high-value exceptions older than SLA", "points": round(age_pen, 2)})
    gst_pen = min(10.0, gst_issues * 2)
    if gst_pen:
        deductions.append({"reason": f"{gst_issues} GST discrepancies", "points": round(gst_pen, 2)})
    cash_pen = min(10.0, blocked / 100000.0 * 4)
    if cash_pen:
        deductions.append({"reason": f"Cash blocked in exceptions {format_inr_compact(blocked)}", "points": round(cash_pen, 2)})
    if refund_spike:
        deductions.append({"reason": "Refund volume is unusually high versus the prior 7 days", "points": refund_spike})
    anom_pen = min(8.0, anomaly_n * 2)
    if anom_pen:
        deductions.append({"reason": f"{anomaly_n} unusual activity signal(s)", "points": round(anom_pen, 2)})

    score = max(0, min(100, round(100 - sum(item["points"] for item in deductions))))
    explanation = "Score is 100 minus transparent penalties."
    if deductions:
        top = max(deductions, key=lambda item: item["points"])
        explanation = f"Score reduced because {top['reason'].lower()}."
    return {
        "score": score,
        "max": 100,
        "deductions": deductions,
        "explanation": explanation,
        "formula": (
            "100 − (1 − match_rate)×30 − min(25, unresolved_lakh×5) − min(15, high_priority×3) "
            "− min(10, aged_high×4) − min(10, gst_issues×2) − min(10, blocked_lakh×4) "
            "− refund_spike(8) − min(8, anomalies×2)."
        ),
        "unresolved_open": unresolved,
    }


def performance_metrics(metrics: dict, resolutions: dict | None, validation: dict | None) -> dict:
    total = int((metrics or {}).get("total_records") or 0)
    matched = int((metrics or {}).get("matched") or 0)
    exceptions = int((metrics or {}).get("exceptions") or 0)
    resolutions = resolutions or {}
    investigated = [item for item in resolutions.values() if item.get("action") in {"investigate", "acknowledge"}]
    auto_resolved = [item for item in resolutions.values() if item.get("action") in {"apply_fix", "waive"} and item.get("status") in {"resolved", "waived"}]
    human = [item for item in resolutions.values() if item.get("action") in {"escalate", "reject", "approve", "waive"}]
    unresolved = int((metrics or {}).get("unresolved_exceptions") or exceptions)
    refused = [item for item in resolutions.values() if item.get("action") in {"escalate", "reject"}]
    ai_rate = round(len(auto_resolved) / exceptions, 4) if exceptions else 0.0
    human_rate = round((len(human) + unresolved) / max(exceptions, 1), 4) if exceptions else 0.0
    payload = {
        "total_records_processed": total,
        "automatically_matched": matched,
        "ai_investigated": len(investigated),
        "automatically_resolved": len(auto_resolved),
        "human_reviewed": len(human),
        "unresolved": unresolved,
        "ai_resolution_rate": ai_rate,
        "human_intervention_rate": human_rate,
        "cases_ai_refused": len(refused),
        "throughput_rps": (metrics or {}).get("records_per_second"),
        "false_positives": None,
        "false_negatives": None,
        "precision": None,
        "recall": None,
        "note": "AI declined cases are escalations/rejections where evidence was insufficient to auto-fix.",
    }
    if validation:
        payload["false_positives"] = validation.get("false_positives")
        payload["false_negatives"] = validation.get("false_negatives") or validation.get("missed")
        payload["precision"] = validation.get("precision")
        payload["recall"] = validation.get("recall")
        payload["ground_truth_available"] = True
    else:
        payload["ground_truth_available"] = False
    return payload


def merchant_profiles(reconciled: pd.DataFrame, resolutions: dict | None = None) -> list[dict]:
    if reconciled is None or reconciled.empty or "customer_id" not in reconciled.columns:
        return []
    profiles = []
    for cid, group in reconciled.groupby(reconciled["customer_id"].astype(str)):
        if cid in {"nan", "None", ""}:
            continue
        total = int(len(group))
        matched = int((group["reconciliation_status"] == "matched").sum()) if "reconciliation_status" in group.columns else 0
        exceptions = group[group["reconciliation_status"] == "exception"] if "reconciliation_status" in group.columns else group.iloc[0:0]
        open_exc = exceptions
        if resolutions:
            keep = [pid for pid in exceptions["payment_id"] if not ((resolutions.get(pid) or {}).get("status") in {"resolved", "waived"})]
            open_exc = exceptions[exceptions["payment_id"].isin(keep)]
        refunds = pd.to_numeric(group.get("refund_amount"), errors="coerce").fillna(0)
        gmv = _num(group, "amount")
        created = pd.to_datetime(group["created_at"], errors="coerce")
        settled = pd.to_datetime(group["settled_at"], errors="coerce") if "settled_at" in group.columns else None
        delay = 0.0
        if settled is not None:
            delay = float(((settled - created).dt.days).dropna().mean() or 0)
        types = {}
        if len(open_exc) and "mismatch_type" in open_exc.columns:
            types = {str(k): int(v) for k, v in open_exc["mismatch_type"].value_counts().items()}
        profiles.append({
            "customer_id": cid,
            "transaction_volume": total,
            "transaction_value_rupees": paise_to_rupees(gmv),
            "reconciliation_rate": round(matched / total, 4) if total else 0,
            "exception_count": int(len(open_exc)),
            "unresolved_value_rupees": paise_to_rupees(_num(open_exc, "amount")),
            "refund_rate": round(float(refunds.sum()) / gmv, 4) if gmv else 0,
            "settlement_delay_days": round(delay, 2),
            "recurring_discrepancies": types,
            "recent_activity": max((ts.isoformat() for ts in created.dropna()), default=None),
            "summary": (
                f"{cid} processed {format_inr_compact(paise_to_rupees(gmv))} with a "
                f"{round(matched / total * 100, 1) if total else 0}% reconciliation rate. "
                f"{int(len(open_exc))} open exceptions affect {format_inr_compact(paise_to_rupees(_num(open_exc, 'amount')))}."
            ),
        })
    profiles.sort(key=lambda item: item["unresolved_value_rupees"], reverse=True)
    return profiles[:40]


def record_timeline(row: dict, audit: list, investigation: dict | None, resolution: dict | None) -> list[dict]:
    events = []
    def add(ts, event_type, record_id, amount, source, actor):
        if not ts:
            return
        events.append({
            "timestamp": ts if isinstance(ts, str) else (ts.isoformat() if hasattr(ts, "isoformat") else str(ts)),
            "event_type": event_type,
            "record_id": record_id,
            "amount_rupees": paise_to_rupees(amount) if amount not in (None, "") else None,
            "source": source,
            "actor": actor,
        })

    created = json_safe(row.get("created_at"))
    add(created, "payment_received", row.get("payment_id"), row.get("amount"), row.get("source") or "payments", "system")
    if row.get("settlement_id"):
        add(json_safe(row.get("settled_at")) or created, "settlement_created", row.get("settlement_id"), row.get("settlement_amount"), "settlements", "system")
    if _num(row, "fee"):
        add(created, "fee_applied", row.get("payment_id"), row.get("fee"), "fees", "rule_engine")
    if _num(row, "tax"):
        add(created, "gst_applied", row.get("payment_id"), row.get("tax"), "gst", "rule_engine")
    if _num(row, "refund_amount"):
        add(created, "refund_initiated", row.get("payment_id"), row.get("refund_amount"), "refunds", "system")
    if row.get("reconciliation_status"):
        add(created, "reconciliation_performed", row.get("payment_id"), row.get("amount"), "rule_engine", "rule_engine")
    if row.get("reconciliation_status") == "exception":
        add(created, "exception_detected", row.get("exception_id") or row.get("payment_id"), row.get("amount"), "rule_engine", "rule_engine")
    if investigation:
        add(investigation.get("investigated_at"), "ai_investigation", row.get("payment_id"), None, "ops_controller", "finance_ops")
    if resolution:
        add(resolution.get("at"), "human_resolution", row.get("payment_id"), None, "ops_controller", resolution.get("actor") or "finance_ops")
    for item in audit or []:
        ids = str(item.get("record_ids") or "")
        if str(row.get("payment_id")) in ids or str(row.get("settlement_id") or "") in ids:
            add(item.get("timestamp"), item.get("action_type") or "audit", item.get("record_ids"), None, item.get("source"), item.get("actor") or item.get("source"))

    events.sort(key=lambda item: item["timestamp"] or "")
    # de-dupe exact timestamp+type
    seen = set()
    unique = []
    for event in events:
        key = (event["timestamp"], event["event_type"], event["record_id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(event)
    return unique


def match_resolution_memory(row: dict, memories: list[dict], rules: list[dict]) -> dict:
    mismatch = str(row.get("mismatch_type") or "")
    method = str(row.get("payment_method") or "")
    merchant = str(row.get("customer_id") or row.get("gstin") or "")
    amount = _num(row, "amount")
    similar = []
    for mem in memories:
        if str(mem.get("mismatch_type") or "") != mismatch:
            continue
        score = 0.55
        if method and str(mem.get("payment_method") or "") == method:
            score += 0.2
        if merchant and str(mem.get("merchant_key") or "") == merchant:
            score += 0.15
        mem_amt = float(mem.get("amount_paise") or 0)
        if mem_amt and amount and abs(mem_amt - amount) / max(mem_amt, amount) <= 0.2:
            score += 0.1
        similar.append({**mem, "similarity": round(min(score, 0.95), 4)})
    similar.sort(key=lambda item: item["similarity"], reverse=True)
    matched_rules = []
    for rule in rules:
        if not int(rule.get("enabled") or 0):
            continue
        if str(rule.get("origin") or "human") != "human":
            continue
        if rule.get("mismatch_type") and str(rule["mismatch_type"]) != mismatch:
            continue
        if rule.get("payment_method") and str(rule["payment_method"]).lower() != method.lower():
            continue
        if rule.get("merchant_key") and str(rule["merchant_key"]) != merchant:
            continue
        matched_rules.append(rule)
    recommendation = None
    confidence = 0.0
    if similar:
        top = similar[0]
        confidence = min(0.92, 0.5 + 0.03 * min(len(similar), 14))
        recommendation = (
            f"This exception resembles {len(similar)} previously resolved {mismatch.replace('_', ' ')} case(s). "
            f"Historical resolution: {top.get('resolution_category') or top.get('human_decision')}."
        )
    return {
        "similar_count": len(similar),
        "similar": similar[:8],
        "matched_rules": matched_rules,
        "recommendation": recommendation,
        "confidence": round(confidence, 4),
        "auto_applied": False,
    }


def proposed_chat_action(question: str, last_payment_id: str | None = None) -> dict | None:
    q = (question or "").strip()
    lowered = q.lower()
    pid_match = re.search(r"\b(pay_[a-z0-9]+)\b", lowered)
    pid = pid_match.group(1) if pid_match else last_payment_id
    if re.search(r"\b(confirm|yes,?\s*proceed|approved?)\b", lowered) and "not" not in lowered:
        return {"type": "confirm_pending"}
    action = None
    if re.search(r"mark .{0,40}investigat", lowered) or "mark it as investigating" in lowered:
        action = "investigate"
    elif re.search(r"\b(resolve|apply (the )?fix|auto-?fix)\b", lowered) and "show" not in lowered:
        action = "apply_fix"
    elif "escalate" in lowered:
        action = "escalate"
    elif "waive" in lowered:
        action = "waive"
    if not action:
        return None
    if not pid:
        return {"type": "need_payment_id", "action": action}
    return {
        "type": "propose",
        "action": action,
        "payment_id": pid,
        "requires_confirmation": True,
    }
