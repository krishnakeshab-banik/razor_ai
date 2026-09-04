"""
Deterministic tools the finance assistant may call. The LLM never computes
these values; it only explains JSON that these functions return.
"""

from __future__ import annotations

import re

from datetime import datetime, timedelta

import pandas as pd

from cash import cash_alerts, compute_cash_position, what_if
from controller_intel import (
    cash_gap, cluster_exceptions, compare_periods,
    detect_anomalies, parse_search_query, proposed_chat_action, refund_intelligence,
    search_finance,
)
from investigate import explain_difference, investigate
from recurrence import detect_recurring
from serialize import json_safe, paise_to_rupees
from time_filters import apply_range, format_day_label, resolve_range


def _rupee_amount(text: str) -> float | None:
    match = re.search(r"(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakh|lac|l)?", text, re.I)
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    if match.group(2):
        value *= 100000
    return value


def _payment_id(text: str) -> str | None:
    match = re.search(r"\b(pay_[a-z0-9]+)\b", text, re.I)
    return match.group(1) if match else None


def get_batch_summary(reconciled: pd.DataFrame) -> dict:
    if reconciled is None or getattr(reconciled, "empty", True):
        return {
            "total_records": 0,
            "matched": 0,
            "exceptions": 0,
            "match_rate": 0,
            "unresolved_rupees": 0,
            "types": {},
            "gmv_rupees": 0,
            "settlement_rupees": 0,
        }
    total = len(reconciled)
    matched = int((reconciled["reconciliation_status"] == "matched").sum()) if "reconciliation_status" in reconciled.columns else 0
    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"] if "reconciliation_status" in reconciled.columns else reconciled.iloc[0:0]
    gmv = paise_to_rupees(pd.to_numeric(reconciled["amount"], errors="coerce").fillna(0).sum()) if "amount" in reconciled.columns else 0
    settlement = paise_to_rupees(pd.to_numeric(reconciled["settlement_amount"], errors="coerce").fillna(0).sum()) if "settlement_amount" in reconciled.columns else 0
    return {
        "total_records": total,
        "matched": matched,
        "exceptions": int(len(exceptions)),
        "match_rate": round(matched / total, 4) if total else 0,
        "unresolved_rupees": paise_to_rupees(pd.to_numeric(exceptions["amount"], errors="coerce").fillna(0).sum()) if len(exceptions) else 0,
        "types": {str(k): int(v) for k, v in exceptions["mismatch_type"].fillna("unclassified").value_counts().items()} if len(exceptions) else {},
        "gmv_rupees": gmv,
        "settlement_rupees": settlement,
    }


def get_high_priority_exceptions(reconciled: pd.DataFrame, limit: int = 8) -> list:
    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"].copy()
    if exceptions.empty:
        return []
    rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    exceptions["_rank"] = exceptions["priority"].map(rank).fillna(3)
    exceptions["_amt"] = pd.to_numeric(exceptions["amount"], errors="coerce").fillna(0)
    exceptions = exceptions.sort_values(["_rank", "_amt"], ascending=[True, False])
    cols = ["payment_id", "mismatch_type", "priority", "amount", "delta"]
    return [{key: json_safe(rec[key]) for key in cols if key in rec} for rec in exceptions[cols].head(limit).to_dict(orient="records")]


def search_transactions(reconciled: pd.DataFrame, question: str, min_rupees: float | None = None) -> list:
    frame = reconciled
    q = question.lower()
    pid = _payment_id(question)
    if pid:
        frame = frame[frame["payment_id"].astype(str).str.lower() == pid.lower()]
    if "refund" in q:
        frame = frame[pd.to_numeric(frame["refund_amount"], errors="coerce").fillna(0) > 0]
    if "unresolved" in q or "exception" in q:
        frame = frame[frame["reconciliation_status"] == "exception"]
    if min_rupees:
        frame = frame[pd.to_numeric(frame["amount"], errors="coerce").fillna(0) >= min_rupees * 100]
    cols = [col for col in ["payment_id", "mismatch_type", "amount", "settlement_amount", "reconciliation_status", "priority"] if col in frame.columns]
    return [{key: json_safe(rec[key]) for key in cols} for rec in frame[cols].head(12).to_dict(orient="records")]


def _latest_stamp(frame: pd.DataFrame) -> str | None:
    if frame is None or frame.empty or "created_at" not in frame.columns:
        return None
    latest_ts = pd.to_datetime(frame["created_at"], errors="coerce").max()
    if pd.isna(latest_ts):
        return None
    return latest_ts.strftime("%Y-%m-%d")


def day_settlement_compare(reconciled: pd.DataFrame, stamp: str | None) -> dict:
    """Compare settlement totals for a batch day vs the previous calendar day in the books."""
    books = reconciled if reconciled is not None else pd.DataFrame()
    day = stamp or _latest_stamp(books)
    if not day:
        return {"note": "No capture dates in this batch."}
    try:
        prev = (datetime.fromisoformat(day) - timedelta(days=1)).strftime("%Y-%m-%d")
    except ValueError:
        return {"note": "Date was invalid."}
    current = apply_range(books, "created_at", resolve_range("custom", start=day, end=day))
    previous = apply_range(books, "created_at", resolve_range("custom", start=prev, end=prev))
    cur = get_batch_summary(current)
    prev_stats = get_batch_summary(previous)
    return {
        "current_date": day,
        "current_label": format_day_label(day),
        "previous_date": prev,
        "previous_label": format_day_label(prev),
        "current": cur,
        "previous": prev_stats,
        "settlement_delta_rupees": round((cur.get("settlement_rupees") or 0) - (prev_stats.get("settlement_rupees") or 0), 2),
        "gmv_delta_rupees": round((cur.get("gmv_rupees") or 0) - (prev_stats.get("gmv_rupees") or 0), 2),
        "note": "These figures are summed from reconciled rows. Do not invent amounts.",
    }


def run_tools(question: str, reconciled: pd.DataFrame, resolutions: dict | None = None, full_df: pd.DataFrame | None = None, scope: dict | None = None) -> dict:
    """Always runs. Returns structured JSON the model may describe, not invent."""
    q = question.lower()
    used = []
    payload = {}
    scope = scope or {}
    books = full_df if full_df is not None and not getattr(full_df, "empty", True) else reconciled

    payload["batch_summary"] = get_batch_summary(reconciled)
    used.append("get_batch_summary")

    settlement_probe = "settlement" in q and any(word in q for word in ("lower", "higher", "less", "more", "drop", "down", "short", "why"))
    if settlement_probe or "what changed" in q or "compared" in q or "versus" in q or "vs yesterday" in q:
        stamp = scope.get("date") or _latest_stamp(books)
        payload["settlement_compare"] = day_settlement_compare(books, stamp)
        used.append("day_settlement_compare")
        versus = "7d" if "7" in q else "yesterday"
        as_of = None
        if stamp:
            try:
                as_of = datetime.fromisoformat(stamp[:10])
            except ValueError:
                as_of = None
        try:
            payload["what_changed"] = compare_periods(books, resolutions, 0.0, 0.0, [], versus, as_of=as_of)
            used.append("compare_periods")
        except (TypeError, AttributeError, KeyError, ValueError):
            payload["what_changed"] = {"note": "Period comparison needs a full reconciled batch with capture dates."}

    if any(term in q for term in ("cash", "forecast", "tomorrow", "position", "liquidity", "shortfall")):
        cash = compute_cash_position(reconciled)
        payload["cash"] = cash
        payload["cash_alerts"] = cash_alerts(cash)
        used.extend(["get_cash_position", "get_forecast"])

    if "what happens" in q or "what-if" in q or "what if" in q or "delayed" in q:
        delayed = _rupee_amount(q) or 0
        drop = "not received" in q or "unresolved" in q and "not" in q
        refund_pct = 20 if "refund" in q and "20" in q else 0
        payload["what_if"] = what_if(
            reconciled,
            delay_settlement_rupees=delayed if "delay" in q or "delayed" in q else 0,
            refund_increase_pct=refund_pct,
            drop_unresolved=drop,
            extra_payout_rupees=delayed if "payout" in q else 0,
        )
        used.append("what_if")

    pid = _payment_id(question)
    if pid:
        lookup = books if books is not None and not getattr(books, "empty", True) else reconciled
        payload["investigation"] = investigate(lookup, pid, resolutions)
        hits = lookup["payment_id"] == pid if lookup is not None and not lookup.empty and "payment_id" in lookup.columns else pd.Series(dtype=bool)
        payload["difference"] = explain_difference(
            lookup[lookup["payment_id"] == pid].iloc[-1].to_dict()
        ) if hits.any() else None
        used.extend(["investigate_exception", "calculate_difference"])

    if "highest" in q or "high priority" in q or "impact" in q:
        payload["high_priority_exceptions"] = get_high_priority_exceptions(reconciled)
        used.append("get_high_priority_exceptions")

    if "recurring" in q or "again" in q or "keeps happening" in q or "cluster" in q:
        payload["recurring"] = detect_recurring(reconciled)
        payload["clusters"] = cluster_exceptions(reconciled, resolutions)
        used.extend(["get_recurring_discrepancies", "find_recurring_issues"])

    if "briefing" in q or "today" in q and "attention" in q:
        used.append("get_action_queue")

    if "gst" in q or "tax line" in q or "18% of fee" in q:
        from ledgers import build_tax_lines
        tax = build_tax_lines(reconciled)
        mismatched_ids = [
            line.get("payment_id")
            for line in tax.get("lines", [])
            if line.get("status") == "mismatch"
        ][:8]
        payload["tax"] = {
            "expected_gst_rupees": tax.get("expected_gst_rupees"),
            "actual_gst_rupees": tax.get("actual_gst_rupees"),
            "delta_rupees": tax.get("delta_rupees"),
            "mismatched_lines": tax.get("mismatched_lines"),
            "matched_lines": tax.get("matched_lines"),
            "sample_mismatch_ids": mismatched_ids,
            "rate": tax.get("rate"),
            "lines": [
                {
                    "payment_id": line.get("payment_id"),
                    "fee_rupees": line.get("fee_rupees"),
                    "expected_gst_rupees": line.get("expected_gst_rupees"),
                    "actual_gst_rupees": line.get("actual_gst_rupees"),
                    "delta_rupees": line.get("delta_rupees"),
                    "status": line.get("status"),
                }
                for line in (tax.get("lines") or [])[:25]
            ],
        }
        used.append("get_tax_lines")

    if "withdraw" in q or "payout" in q:
        cash = payload.get("cash") or compute_cash_position(reconciled)
        payload["cash"] = cash
        payload["withdrawable_rupees"] = cash.get("available_rupees")
        used.append("get_cash_position")

    if "why" in q and "cash" in q:
        cash = payload.get("cash") or compute_cash_position(reconciled)
        payload["cash_gap"] = cash_gap(reconciled, cash)
        used.append("calculate_cash_position")

    if "anomal" in q or "unusual" in q:
        payload["anomalies"] = detect_anomalies(reconciled)
        used.append("find_anomalies")

    if "refund spike" in q or "investigate refund" in q:
        payload["refund_intel"] = refund_intelligence(reconciled)
        used.append("get_refund")

    min_rupees = _rupee_amount(q) if "above" in q or "greater" in q or ">" in q else None
    if any(term in q for term in ("show", "list", "unresolved", "refund", "search", "which", "find")):
        payload["search"] = search_transactions(reconciled, question, min_rupees)
        payload["finance_search"] = search_finance(reconciled, question, resolutions=resolutions)
        payload["parsed_query"] = parse_search_query(question)
        used.extend(["search_transactions", "search_financial_records"])

    proposed = proposed_chat_action(question)
    if proposed:
        payload["proposed_action"] = proposed
        used.append("propose_action")

    payload["tools_used"] = used
    return payload


VISUAL_TOOLS = (
    "get_tax_lines",
    "compare_periods",
    "get_recurring_discrepancies",
    "get_high_priority_exceptions",
    "get_forecast",
    "get_cash_position",
    "search_financial_records",
)


def _json_safe_tree(value):
    if isinstance(value, dict):
        return {str(key): _json_safe_tree(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_tree(item) for item in value]
    return json_safe(value)


def _payload_for_visual_tool(name: str, payload: dict):
    if name == "get_tax_lines":
        return payload.get("tax")
    if name == "compare_periods":
        return payload.get("what_changed")
    if name == "get_recurring_discrepancies":
        return payload.get("recurring")
    if name == "get_high_priority_exceptions":
        return payload.get("high_priority_exceptions")
    if name in {"get_forecast", "get_cash_position"}:
        return payload.get("cash")
    if name == "search_financial_records":
        return payload.get("search")
    return None


def visual_tool_result(payload: dict | None) -> tuple[str | None, object | None]:
    """Pick the primary visual tool and return its raw JSON for the UI."""
    payload = payload or {}
    used = payload.get("tools_used") or []
    picked = next((name for name in VISUAL_TOOLS if name in used), None)
    if not picked:
        return None, None
    data = _payload_for_visual_tool(picked, payload)
    if data is None:
        return None, None
    return picked, _json_safe_tree(data)
