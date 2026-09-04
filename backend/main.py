"""
Razor-AI backend. Thin FastAPI layer that wires together:
- reconciliation.py  (deterministic matching -- no AI)
- explanations.py    (deterministic templates -- no AI)
- chatbot.py          (the ONLY AI component, Gemini-powered)
- cash.py             (cash position + 7-day forecast)
- resolution.py       (closes the exception loop)
- ledgers.py          (payments vs settlements vs bank + GST lines)
- database.py         (SQLite audit trail)

Run locally:
    uvicorn main:app --reload --port 8000
    Then visit http://localhost:8000/docs
"""

from __future__ import annotations

from io import BytesIO
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from data.generate_data import generate_batch

from cash import cash_alerts, compute_cash_position, what_if
from catalog import list_payments, public_payment, search_exceptions
from chatbot import ask, chat_copy
from config import ALLOWED_GENERATE_COUNTS, MAX_UPLOAD_BYTES, public_config
from controller_intel import (
    action_queue, build_briefing, cash_gap, cluster_exceptions, compare_periods,
    detect_anomalies, exception_aging, health_score, match_resolution_memory,
    merchant_profiles, metrics_from_frame, performance_metrics, proposed_chat_action,
    record_timeline, refund_intelligence, search_finance, snapshot_payload,
)
from demo_payment import VALID_OUTCOMES, apply_refund, build_demo_transaction, map_razorpay_payment
import razorpay_gateway
from database import (
    init_db, log_audit, get_audit_trail, reset_db,
    save_investigation, save_analyst_note, list_analyst_notes,
    clear_notifications, clear_withdrawals, sum_withdrawn_paise,
    insert_store_order, list_store_orders, get_store_order, update_store_order_refund,
    save_metric_snapshot, list_metric_snapshots,
    insert_resolution_memory, list_resolution_memory,
    insert_controller_rule, list_controller_rules, get_controller_rule,
    update_controller_rule, delete_controller_rule, bump_rule_influence,
    get_investigation,
)
from explainations import explain
from ingest import inspect_bytes, normalize_batch
from investigate import dump_investigation, explain_difference, investigate
from ledgers import build_source_view, build_tax_lines
from notifications import mark_all_read, mark_read, notifications_payload, notify_new_exceptions, notify_payment_captured, notify_refund
from reconciliation import reconcile, compute_metrics, evaluate_against_answer_key
from recurrence import detect_recurring
from reports import build_excel_report, build_word_report
from resolution import apply_fix, auto_fixable_ids, stamp_resolution, suggest
from serialize import json_safe, paise_to_rupees
from time_filters import apply_range, format_day_label, resolve_range
import withdrawals as withdrawal_service

app = FastAPI(title="Razor-AI Finance Controller API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

init_db()

_state = {
    "transactions": None,
    "reconciled": None,
    "answer_key": None,
    "resolutions": {},
    "last_validation": None,
    "batch_meta": None,
    "last_ingest": None,
    "history_recurrence": [],
    "snapshots": [],
    "pending_chat_action": None,
    "last_focus_payment_id": None,
    "razorpay_pending": {},
}


class ChatRequest(BaseModel):
    question: str
    date: str | None = None
    preset: str | None = None
    start: str | None = None
    end: str | None = None
    batch_id: str | None = None
    language: str | None = None


class DemoPaymentRequest(BaseModel):
    amount_rupees: float
    outcome: str = "clean"
    items: list[dict] | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    payment_method: str | None = None


class RazorpayCreateOrderRequest(BaseModel):
    amount_rupees: float
    outcome: str = "clean"
    items: list[dict] | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    payment_method: str | None = None


class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class RefundRequest(BaseModel):
    payment_id: str
    amount_rupees: float | None = None
    confirm: bool = False


class ResolveRequest(BaseModel):
    payment_id: str
    action: str = "apply_fix"
    note: str = ""
    actor: str = "finance_ops"
    remember: bool = False


class BatchResolveRequest(BaseModel):
    payment_ids: list[str] | None = None
    cluster_id: str | None = None
    action: str = "apply_fix"
    note: str = ""
    actor: str = "finance_ops"
    confirm: bool = False
    remember: bool = False


class WhatIfRequest(BaseModel):
    delay_settlement_rupees: float = 0
    refund_increase_pct: float = 0
    drop_unresolved: bool = False
    extra_payout_rupees: float = 0


class WithdrawRequest(BaseModel):
    amount_rupees: float
    as_of: str | None = None


class SearchRequest(BaseModel):
    query: str


class ChatConfirmRequest(BaseModel):
    confirm: bool = False


class RuleCreateRequest(BaseModel):
    title: str
    guidance: str
    mismatch_type: str | None = None
    payment_method: str | None = None
    merchant_key: str | None = None
    resolution_category: str | None = None
    origin: str = "human"
    actor: str = "finance_ops"


class RuleUpdateRequest(BaseModel):
    title: str | None = None
    guidance: str | None = None
    mismatch_type: str | None = None
    payment_method: str | None = None
    merchant_key: str | None = None
    resolution_category: str | None = None
    enabled: bool | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_batch_meta(source: str, count: int, extra: dict | None = None) -> dict:
    meta = {
        "batch_id": f"BTC-{uuid.uuid4().hex[:8].upper()}",
        "source": source,
        "loaded_at": _now_iso(),
        "record_count": count,
    }
    if extra:
        meta.update(extra)
    return meta


def _ingest_demo_rows(
    rows: list[dict],
    *,
    outcome: str,
    items: list[dict] | None,
    customer_name: str | None,
    customer_email: str | None,
    payment_method: str | None,
    audit_source: str,
):
    """Append live checkout rows, reconcile, audit, notify, and persist the store order."""
    new_transactions = pd.DataFrame(rows)
    if _state["transactions"] is None:
        _state["transactions"] = new_transactions
        _state["batch_meta"] = _new_batch_meta("ecommerce_demo", len(new_transactions))
    else:
        _state["transactions"] = pd.concat(
            [_state["transactions"], new_transactions], ignore_index=True
        )
        if _state["batch_meta"]:
            _state["batch_meta"]["record_count"] = int(len(_state["transactions"]))

    _state["reconciled"] = reconcile(_state["transactions"])
    reconciled_rows = _state["reconciled"].tail(len(rows))
    for _, row in reconciled_rows.iterrows():
        row_dict = row.to_dict()
        if row_dict["reconciliation_status"] == "exception":
            log_audit("exception", row_dict["payment_id"], explain(row_dict), audit_source)
        else:
            log_audit("match", row_dict["payment_id"], "Matched within tolerance", audit_source)

    raw = reconciled_rows.iloc[-1].to_dict()
    payment = {key: json_safe(value) for key, value in raw.items()}
    payment["explanation"] = explain(raw)
    payment["suggested_action"] = suggest(raw.get("mismatch_type"))
    created = notify_new_exceptions(
        [row.to_dict() | {"explanation": explain(row.to_dict())} for _, row in reconciled_rows.iterrows()],
        audit_source,
    )
    insert_store_order(
        payment_id=payment["payment_id"],
        order_id=payment.get("order_id"),
        amount_paise=int(float(payment.get("amount") or 0)),
        status=str(payment.get("status") or "captured"),
        outcome=outcome,
        items_json=json.dumps(items or []),
        customer_name=customer_name,
        customer_email=customer_email,
        payment_method=payment_method or str(payment.get("payment_method") or "upi"),
    )
    _capture_snapshot()
    return {
        "this_payment": payment,
        "batch_metrics": _enrich_metrics(compute_metrics(_state["reconciled"])),
        "notifications": created,
    }


def _reset_run_state():
    _state["reconciled"] = None
    _state["resolutions"] = {}
    _state["last_validation"] = None
    _state["pending_chat_action"] = None
    _state["last_focus_payment_id"] = None
    clear_notifications()
    clear_withdrawals()


def _public_store_order(row: dict) -> dict:
    amount = int(row.get("amount_paise") or 0)
    refunded = int(row.get("refunded_paise") or 0)
    items = []
    raw_items = row.get("items_json")
    if raw_items:
        try:
            items = json.loads(raw_items)
        except (TypeError, json.JSONDecodeError):
            items = []
    return {
        "payment_id": row.get("payment_id"),
        "order_id": row.get("order_id"),
        "created_at": row.get("created_at"),
        "amount_rupees": paise_to_rupees(amount),
        "refunded_rupees": paise_to_rupees(refunded),
        "remaining_rupees": paise_to_rupees(max(0, amount - refunded)),
        "status": row.get("status"),
        "outcome": row.get("outcome"),
        "items": items,
        "customer_name": row.get("customer_name"),
        "customer_email": row.get("customer_email"),
        "payment_method": row.get("payment_method"),
        "refundable": amount - refunded > 0,
    }


def _remember_resolution(row: dict, record: dict, note: str):
    insert_resolution_memory(
        payment_id=row.get("payment_id"),
        mismatch_type=str(row.get("mismatch_type") or record.get("mismatch_type") or "unknown"),
        root_cause=str(row.get("mismatch_type") or ""),
        resolution_category=record.get("action") or record.get("status"),
        payment_method=str(row.get("payment_method") or ""),
        merchant_key=str(row.get("customer_id") or row.get("gstin") or ""),
        human_decision=note or record.get("note") or record.get("action"),
        evidence=str(row.get("payment_id")),
        amount_paise=int(float(row.get("amount") or 0)),
        actor=record.get("actor") or "finance_ops",
    )


def _capture_snapshot():
    if _state["reconciled"] is None:
        return
    cash = _cash_view(_state["reconciled"])
    numbers = metrics_from_frame(
        _state["reconciled"],
        _state["resolutions"],
        cash.get("withdrawn_rupees") or 0,
        cash.get("available_rupees"),
    )
    snap = snapshot_payload((_state["batch_meta"] or {}).get("batch_id"), numbers)
    _state["snapshots"] = [snap] + [item for item in _state["snapshots"] if item.get("batch_id") != snap.get("batch_id")][:19]
    save_metric_snapshot(snap.get("batch_id"), json.dumps(snap))


def _loaded_snapshots() -> list[dict]:
    if _state["snapshots"]:
        return _state["snapshots"]
    stored = []
    for row in list_metric_snapshots(20):
        try:
            stored.append(json.loads(row["payload"]))
        except (TypeError, json.JSONDecodeError):
            continue
    _state["snapshots"] = stored
    return stored


def _controller_pack(versus: str = "yesterday") -> dict:
    reconciled = _require_reconciled()
    cash = _cash_view(reconciled)
    tax = build_tax_lines(reconciled)
    withdrawn = float(cash.get("withdrawn_rupees") or 0)
    clusters = cluster_exceptions(reconciled, _state["resolutions"])
    aging = exception_aging(reconciled, _state["resolutions"])
    anomalies = detect_anomalies(reconciled)
    refunds = refund_intelligence(reconciled)
    metrics = _enrich_metrics(compute_metrics(reconciled))
    changes = compare_periods(
        reconciled, _state["resolutions"], withdrawn, cash.get("available_rupees") or 0,
        _loaded_snapshots(), versus,
        current_batch_id=(_state["batch_meta"] or {}).get("batch_id"),
    )
    briefing = build_briefing(
        reconciled, cash, tax, _state["resolutions"], withdrawn, clusters,
        changes.get("changes") or [], aging.get("alerts") or [],
    )
    queue = action_queue(reconciled, clusters, cash, tax, aging, anomalies, refunds, _state["resolutions"])
    health = health_score(metrics, cash, tax, aging, anomalies, refunds)
    performance = performance_metrics(metrics, _state["resolutions"], _state["last_validation"])
    return {
        "briefing": briefing,
        "what_changed": changes,
        "clusters": clusters,
        "action_queue": queue,
        "health": health,
        "aging": aging,
        "anomalies": anomalies,
        "refunds": refunds,
        "performance": performance,
        "cash_gap": cash_gap(reconciled, cash, withdrawn),
        "merchants": merchant_profiles(reconciled, _state["resolutions"]),
    }


def _cash_view(reconciled) -> dict:
    position = compute_cash_position(reconciled)
    withdrawn = paise_to_rupees(sum_withdrawn_paise())
    earned = float(position.get("available_rupees") or 0)
    available = round(max(0.0, earned - withdrawn), 2)
    position["earned_available_rupees"] = earned
    position["withdrawn_rupees"] = withdrawn
    position["available_rupees"] = available
    position["expected_incoming_rupees"] = position.get("in_transit_rupees") or 0.0
    position["expected_outgoing_rupees"] = 0.0
    position["unresolved_amount_rupees"] = position.get("blocked_rupees") or 0.0
    position["projected_cash_rupees"] = round(available + float(position.get("in_transit_rupees") or 0), 2)
    position["alerts"] = cash_alerts(position)
    position["recurring"] = detect_recurring(reconciled, _state["history_recurrence"])
    return position


def _normalize_batch_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized, report = normalize_batch(df)
    _state["last_ingest"] = report
    return normalized


def _require_batch() -> pd.DataFrame:
    if _state["transactions"] is None:
        raise HTTPException(status_code=400, detail="No batch loaded. Call /batch/load first.")
    return _state["transactions"]


def _require_reconciled() -> pd.DataFrame:
    if _state["reconciled"] is None:
        raise HTTPException(status_code=400, detail="Reconciliation has not been run yet.")
    return _state["reconciled"]


def _enrich_metrics(metrics: dict) -> dict:
    resolved = [item for item in _state["resolutions"].values() if item.get("status") in {"resolved", "waived"}]
    escalated = [item for item in _state["resolutions"].values() if item.get("status") == "escalated"]
    metrics["resolved_count"] = len(resolved)
    metrics["escalated_count"] = len(escalated)
    if _state["reconciled"] is not None:
        exception_ids = _state["reconciled"].loc[
            _state["reconciled"]["reconciliation_status"] == "exception", "payment_id"
        ]
        metrics["unresolved_exceptions"] = int(sum(1 for pid in exception_ids if not _is_closed(pid)))
    else:
        metrics["unresolved_exceptions"] = metrics.get("exceptions", 0)
    if _state["last_validation"] is not None:
        metrics["validation"] = _state["last_validation"]
    if _state["batch_meta"] is not None:
        metrics["batch"] = _state["batch_meta"]
    if _state["last_ingest"] is not None:
        metrics["ingest"] = {
            "detected_source": _state["last_ingest"].get("detected_source"),
            "warnings": _state["last_ingest"].get("warnings"),
            "malformed_count": _state["last_ingest"].get("malformed_count"),
            "units": _state["last_ingest"].get("units"),
        }
    metrics["config"] = public_config()
    return metrics


def _list_exceptions(include_closed: bool = False) -> list:
    reconciled = _require_reconciled()
    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"]
    result = []
    for _, row in exceptions.iterrows():
        payload = _public_exception(row.to_dict())
        if include_closed or payload["open"]:
            result.append(payload)
    result.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return result


def _run_reconciliation(log_source: str = "rule_engine") -> dict:
    transactions = _require_batch()
    reconciled = reconcile(transactions)
    _state["reconciled"] = reconciled

    matched = 0
    for _, row in reconciled.iterrows():
        row_dict = row.to_dict()
        if row_dict["reconciliation_status"] == "exception":
            log_audit("exception", row_dict["payment_id"], explain(row_dict), log_source)
        else:
            matched += 1
    log_audit(
        "match",
        _state["batch_meta"]["batch_id"] if _state["batch_meta"] else "-",
        f"Matched {matched} of {len(reconciled)} records",
        log_source,
    )

    metrics = compute_metrics(reconciled)
    if _state["answer_key"] is not None and _state["last_validation"] is None:
        _state["last_validation"] = evaluate_against_answer_key(reconciled, _state["answer_key"])
    notify_new_exceptions(
        [
            {**row.to_dict(), "explanation": explain(row.to_dict())}
            for _, row in reconciled.iterrows()
        ],
        log_source,
    )
    enriched = _enrich_metrics(metrics)
    _capture_snapshot()
    return enriched


def _is_closed(payment_id: str) -> bool:
    item = _state["resolutions"].get(payment_id)
    return bool(item and item.get("status") in {"resolved", "waived"})


def _public_exception(row_dict: dict) -> dict:
    suggestion = suggest(row_dict.get("mismatch_type"))
    resolution = _state["resolutions"].get(row_dict["payment_id"])
    evidence = row_dict.get("evidence")
    if evidence is not None and not isinstance(evidence, list):
        evidence = []
    workflow = (resolution or {}).get("workflow_status") or ("Open" if row_dict.get("reconciliation_status") == "exception" else "Resolved")
    return {
        "payment_id": row_dict["payment_id"],
        "exception_id": json_safe(row_dict.get("exception_id")) or f"exc_{row_dict['payment_id']}",
        "order_id": json_safe(row_dict.get("order_id")),
        "customer_id": json_safe(row_dict.get("customer_id")),
        "mismatch_type": row_dict["mismatch_type"],
        "delta": json_safe(row_dict.get("delta")),
        "amount": json_safe(row_dict.get("amount")),
        "fee": json_safe(row_dict.get("fee")),
        "tax": json_safe(row_dict.get("tax")),
        "refund_amount": json_safe(row_dict.get("refund_amount")),
        "adjustment": json_safe(row_dict.get("adjustment")),
        "settlement_amount": json_safe(row_dict.get("settlement_amount")),
        "expected_settlement": json_safe(row_dict.get("expected_settlement")),
        "status": json_safe(row_dict.get("status")),
        "created_at": json_safe(row_dict.get("created_at")),
        "settled_at": json_safe(row_dict.get("settled_at")),
        "priority": row_dict.get("priority", "Low"),
        "confidence": json_safe(row_dict.get("confidence")),
        "match_kind": json_safe(row_dict.get("match_kind")),
        "evidence": evidence or [],
        "workflow_status": workflow,
        "payment_method": json_safe(row_dict.get("payment_method")),
        "gstin": json_safe(row_dict.get("gstin")),
        "source": json_safe(row_dict.get("source")),
        "utr": json_safe(row_dict.get("utr")),
        "explanation": explain(row_dict),
        "suggested_action": suggestion,
        "resolution": resolution,
        "open": not _is_closed(row_dict["payment_id"]),
    }


@app.post("/batch/load")
def load_batch():
    """Loads the synthetic batch generated by data/generate_data.py."""
    batch_path = os.path.join(DATA_DIR, "synthetic_batch.csv")
    if not os.path.exists(batch_path):
        raise HTTPException(
            status_code=404,
            detail="No batch found. Run 'python generate_data.py' in the data/ folder first.",
        )

    df = pd.read_csv(batch_path, parse_dates=["created_at", "settled_at"])
    _state["transactions"] = _normalize_batch_dataframe(df)
    _reset_run_state()

    answer_key_path = os.path.join(DATA_DIR, "answer_key.csv")
    _state["answer_key"] = pd.read_csv(answer_key_path) if os.path.exists(answer_key_path) else None
    _state["batch_meta"] = _new_batch_meta("synthetic_demo", len(_state["transactions"]))
    withdrawal_service.seed_demo_withdrawals()

    return {"loaded": len(_state["transactions"]), "batch": _state["batch_meta"]}


@app.post("/batch/generate-fresh")
def generate_fresh_batch(count: int = 100):
    """Create a new random batch, load it into state, and return the record count."""
    if count not in ALLOWED_GENERATE_COUNTS:
        raise HTTPException(
            status_code=400,
            detail=f"count must be one of {list(ALLOWED_GENERATE_COUNTS)}",
        )
    df, answer_key = generate_batch(num_records=count, seed=None)
    _state["transactions"] = _normalize_batch_dataframe(df)
    _reset_run_state()
    _state["answer_key"] = answer_key
    _state["batch_meta"] = _new_batch_meta("generated", len(_state["transactions"]), {"requested": count})
    withdrawal_service.seed_demo_withdrawals()
    return {"loaded": len(_state["transactions"]), "count": count, "generated": True, "batch": _state["batch_meta"]}


@app.post("/batch/upload")
async def upload_batch(file: UploadFile = File(...)):
    """Uploads a CSV/XLSX file, validates it, and loads it into the engine."""
    contents = await file.read()
    try:
        raw, meta = inspect_bytes(contents, file.filename or "upload.csv")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    df, report = normalize_batch(raw)
    _state["last_ingest"] = report
    _state["transactions"] = df
    _reset_run_state()
    _state["answer_key"] = None
    _state["batch_meta"] = _new_batch_meta(file.filename or "upload", len(df), {
        "detected_source": report.get("detected_source"),
        "malformed_count": report.get("malformed_count"),
    })
    return {
        "loaded": len(df),
        "filename": file.filename,
        "batch": _state["batch_meta"],
        "validation": report,
        "bytes": len(contents),
        "max_bytes": MAX_UPLOAD_BYTES,
    }


@app.get("/batch/status")
def batch_status():
    loaded = _state["transactions"] is not None
    return {
        "loaded": loaded,
        "reconciled": _state["reconciled"] is not None,
        "record_count": 0 if not loaded else int(len(_state["transactions"])),
        "batch": _state["batch_meta"],
        "has_answer_key": _state["answer_key"] is not None,
    }


@app.post("/reconcile/run")
def run_reconciliation():
    """Runs the deterministic reconciliation engine on the loaded batch."""
    return _run_reconciliation()


@app.get("/reconcile/metrics")
def get_metrics():
    reconciled = _require_reconciled()
    return _enrich_metrics(compute_metrics(reconciled))


@app.get("/reconcile/exceptions")
def get_exceptions(include_closed: bool = False):
    return _list_exceptions(include_closed=include_closed)


@app.get("/payments")
def get_payments(
    preset: str = "all",
    start: str | None = None,
    end: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    q: str = "",
    page: int = 1,
    page_size: int = 25,
    status: str = "all",
):
    reconciled = _require_reconciled()
    return list_payments(
        reconciled, _is_closed, preset, start, end, start_time, end_time, q, page, page_size, status,
    )


@app.get("/exceptions/search")
def search_exception_records(
    include_closed: bool = False,
    preset: str = "all",
    start: str | None = None,
    end: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    q: str = "",
    mismatch_type: str = "all",
    page: int = 1,
    page_size: int = 25,
):
    return search_exceptions(
        _list_exceptions(include_closed=include_closed),
        preset, start, end, start_time, end_time, q, mismatch_type, page, page_size,
    )


@app.post("/chat")
def chat(req: ChatRequest):
    reconciled = _state.get("reconciled")
    extra = {
        "product": True,
        "config": {
            "fee_pct": public_config()["fee_pct"],
            "tax_pct": public_config()["tax_pct"],
            "tax_base": public_config()["tax_base"],
            "expected_settlement_days": public_config()["expected_settlement_days"],
            "currency": public_config()["currency"],
        },
    }
    if reconciled is not None and not getattr(reconciled, "empty", True):
        cash = compute_cash_position(reconciled)
        tax = build_tax_lines(reconciled)
        extra["cash"] = {
            "available_rupees": cash.get("available_rupees"),
            "in_transit_rupees": cash.get("in_transit_rupees"),
            "blocked_rupees": cash.get("blocked_rupees"),
            "expected_7d_rupees": cash.get("expected_7d_rupees"),
        }
        extra["tax"] = {
            "expected_gst_rupees": tax.get("expected_gst_rupees"),
            "actual_gst_rupees": tax.get("actual_gst_rupees") or tax.get("gst_collected_rupees"),
            "mismatched_lines": tax.get("mismatched_lines"),
        }
        extra["batch"] = {
            "records": int(len(reconciled)),
            "exceptions": int((reconciled["reconciliation_status"] == "exception").sum()),
        }
        extra["withdrawn_rupees"] = round(sum_withdrawn_paise() / 100, 2)
    extra["scope_requested"] = {
        "date": (req.date or "")[:10] or None,
        "preset": req.preset,
        "start": req.start,
        "end": req.end,
        "batch_id": req.batch_id or (_state.get("batch_meta") or {}).get("batch_id"),
    }
    extra_json = json.dumps(extra)
    pending = _state.get("pending_chat_action")
    proposed = proposed_chat_action(req.question, _state.get("last_focus_payment_id"))
    if proposed and proposed.get("type") == "confirm_pending":
        if not pending:
            return {
                "answer": chat_copy(req.language, "There is no pending finance action to confirm.", "पुष्टि करने के लिए कोई लंबित वित्त क्रिया नहीं है।"),
                "grounded_in": [],
                "tools_used": ["confirm_action"],
                "ai_available": False,
            }
        result = resolve_exception(ResolveRequest(
            payment_id=pending["payment_id"],
            action=pending["action"],
            note="Confirmed via assistant",
            actor="finance_ops",
        ))
        _state["pending_chat_action"] = None
        log_audit("chat_action", pending["payment_id"], f"Confirmed {pending['action']}", "ops_controller")
        return {
            "answer": chat_copy(
                req.language,
                f"Confirmed. {pending['action']} applied to {pending['payment_id']}.",
                f"पुष्टि हो गई। {pending['action']} {pending['payment_id']} पर लागू हुआ।",
            ),
            "grounded_in": [pending["payment_id"]],
            "tools_used": ["update_exception_status"],
            "ai_available": True,
            "executed": result,
        }
    result = ask(
        req.question,
        reconciled if reconciled is not None else pd.DataFrame(),
        extra_context=extra_json,
        resolutions=_state["resolutions"],
        scope={
            "date": (req.date or "")[:10] or None,
            "preset": req.preset,
            "start": req.start,
            "end": req.end,
            "batch_id": req.batch_id or (_state.get("batch_meta") or {}).get("batch_id"),
        },
        language=req.language,
    )
    if result.get("pending_confirmation"):
        _state["pending_chat_action"] = result["pending_confirmation"]
        _state["last_focus_payment_id"] = result["pending_confirmation"].get("payment_id")
    found = re.search(r"\b(pay_[a-z0-9]+)\b", req.question, flags=re.I)
    pid = found.group(1) if found else None
    if pid:
        _state["last_focus_payment_id"] = pid
    log_audit("chat_query", pid or "-", f"Q: {req.question[:240]} | A: {str(result.get('answer') or '')[:400]}", "gemini_api")
    return result


@app.post("/chat/confirm")
def chat_confirm(req: ChatConfirmRequest):
    pending = _state.get("pending_chat_action")
    if not pending:
        raise HTTPException(status_code=400, detail="No pending assistant action to confirm")
    if not req.confirm:
        _state["pending_chat_action"] = None
        return {"cancelled": True, "pending": pending}
    result = resolve_exception(ResolveRequest(
        payment_id=pending["payment_id"],
        action=pending["action"],
        note="Confirmed via assistant",
        actor="finance_ops",
    ))
    _state["pending_chat_action"] = None
    log_audit("chat_action", pending["payment_id"], f"Confirmed {pending['action']}", "ops_controller")
    return {"executed": True, "pending": pending, "result": result}


@app.get("/audit-trail")
def audit_trail(
    limit: int = 100,
    preset: str = "all",
    start: str | None = None,
    end: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    action_type: str | None = None,
    source: str | None = None,
    q: str | None = None,
):
    bounds = resolve_range(preset, start, end, start_time, end_time)
    if bounds.get("inverted"):
        return []
    return get_audit_trail(
        limit=limit,
        start=bounds.get("start"),
        end=bounds.get("end"),
        action_type=action_type,
        source=source,
        q=q,
    )


@app.get("/analytics/summary")
def analytics_summary():
    df = _require_batch().copy()
    if df.empty:
        return {
            "total_orders": 0,
            "total_earnings": 0,
            "total_tax": 0,
            "total_fees": 0,
            "total_refunds": 0,
            "net_settlement": 0,
            "average_order_value": 0,
            "monthly": [],
            "yearly": [],
        }

    created_at = pd.to_datetime(df["created_at"], errors="coerce")
    df["month_label"] = created_at.dt.to_period("M").astype(str)
    df["year_label"] = created_at.dt.year.astype(str)

    def group_payload(label, group):
        return {
            "label": label,
            "orders": int(len(group)),
            "gross": paise_to_rupees(group["amount"].sum()),
            "tax": paise_to_rupees(group["tax"].sum()),
            "fees": paise_to_rupees(group["fee"].sum()),
            "refunds": paise_to_rupees(group["refund_amount"].sum()),
            "net": paise_to_rupees(group["settlement_amount"].fillna(0).sum()),
        }

    monthly = [group_payload(label, group) for label, group in df.groupby("month_label", sort=True)]
    yearly = [group_payload(label, group) for label, group in df.groupby("year_label", sort=True)]

    total_orders = int(len(df))
    total_earnings = paise_to_rupees(df["amount"].sum())
    return {
        "total_orders": total_orders,
        "total_earnings": total_earnings,
        "total_tax": paise_to_rupees(df["tax"].sum()),
        "total_fees": paise_to_rupees(df["fee"].sum()),
        "total_refunds": paise_to_rupees(df["refund_amount"].sum()),
        "net_settlement": paise_to_rupees(df["settlement_amount"].fillna(0).sum()),
        "average_order_value": round(total_earnings / total_orders, 2) if total_orders else 0,
        "monthly": monthly,
        "yearly": yearly,
    }


def _latest_created_date(reconciled) -> str | None:
    if reconciled is None or getattr(reconciled, "empty", True) or "created_at" not in reconciled.columns:
        return None
    latest_ts = pd.to_datetime(reconciled["created_at"], errors="coerce").max()
    if pd.isna(latest_ts):
        return None
    return latest_ts.strftime("%Y-%m-%d")


def _batch_headline(stamp: str | None, batch_id: str | None = None) -> str:
    bid = batch_id or ((_state.get("batch_meta") or {}).get("batch_id")) or "—"
    day = format_day_label(stamp) if stamp else "this batch"
    return f"Summary for {day} · Batch {bid}"


def _frame_for_date(reconciled, date: str | None):
    latest = _latest_created_date(reconciled)
    stamp = (date or "").strip()[:10] or latest
    if stamp:
        bounds = resolve_range("custom", start=stamp, end=stamp)
        label = stamp
    else:
        bounds = resolve_range("all")
        label = "batch"
    frame = apply_range(reconciled, "created_at", bounds) if stamp else reconciled
    return frame, bounds, label, latest, stamp


@app.get("/analytics/day")
def analytics_day(date: str | None = None, payment_id: str | None = None):
    reconciled = _require_reconciled()
    frame, bounds, label, latest, stamp = _frame_for_date(reconciled, date)
    metrics = compute_metrics(frame) if frame is not None and not frame.empty else {
        "total_records": 0, "matched": 0, "exceptions": 0, "mismatch_breakdown": {}, "priority_breakdown": {},
        "amount_reconciled": 0, "amount_at_risk": 0,
    }
    exceptions = []
    if frame is not None and not frame.empty and "reconciliation_status" in frame.columns:
        open_rows = frame[frame["reconciliation_status"] == "exception"]
        for _, row in open_rows.head(12).iterrows():
            exceptions.append({
                "payment_id": json_safe(row.get("payment_id")),
                "mismatch_type": json_safe(row.get("mismatch_type")),
                "priority": json_safe(row.get("priority")),
                "amount_rupees": paise_to_rupees(row.get("amount")),
                "delta_rupees": paise_to_rupees(row.get("delta")) if row.get("delta") is not None else None,
            })
    payment = None
    needle = (payment_id or "").strip()
    if needle:
        ids = reconciled["payment_id"].astype(str)
        hit = reconciled[ids.str.lower() == needle.lower()]
        if hit.empty:
            hit = reconciled[ids.str.lower().str.contains(needle.lower(), na=False)]
        if not hit.empty:
            payment = public_payment(hit.iloc[0].to_dict(), False)
            payment["explanation"] = json_safe(hit.iloc[0].get("explanation"))
            payment["priority"] = json_safe(hit.iloc[0].get("priority"))
            payment["delta"] = json_safe(hit.iloc[0].get("delta"))
    batch_id = (_state.get("batch_meta") or {}).get("batch_id")
    return {
        "date": stamp,
        "label": format_day_label(stamp) if stamp else label,
        "headline": _batch_headline(stamp, batch_id),
        "batch_id": batch_id,
        "latest_date": latest,
        "filter": {key: bounds.get(key) for key in ("preset", "start", "end", "warning") if key in bounds},
        "totals": {
            "count": int(metrics.get("total_records") or 0),
            "matched": int(metrics.get("matched") or 0),
            "exceptions": int(metrics.get("exceptions") or 0),
            "gmv_rupees": paise_to_rupees(frame["amount"].sum()) if frame is not None and not frame.empty else 0,
            "fees_rupees": paise_to_rupees(frame["fee"].sum()) if frame is not None and not frame.empty and "fee" in frame.columns else 0,
            "gst_rupees": paise_to_rupees(frame["tax"].sum()) if frame is not None and not frame.empty and "tax" in frame.columns else 0,
            "amount_at_risk_rupees": paise_to_rupees(metrics.get("amount_at_risk") or 0),
        },
        "mismatch_breakdown": metrics.get("mismatch_breakdown") or {},
        "priority_breakdown": metrics.get("priority_breakdown") or {},
        "exceptions": exceptions,
        "payment": payment,
        "payment_found": bool(payment) if needle else None,
    }


@app.get("/reports/word")
def word_close_report():
    reconciled = _require_reconciled()
    payload = build_word_report(
        metrics=_enrich_metrics(compute_metrics(reconciled)),
        analytics=analytics_summary(),
        exceptions=_list_exceptions(),
        cash=compute_cash_position(reconciled),
        tax=build_tax_lines(reconciled),
        audit=get_audit_trail(limit=20),
        batch_meta=_state.get("batch_meta"),
    )
    log_audit("report_export", "-", "Word close report downloaded", "ops_controller")
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="razorai-close-report.docx"'},
    )


@app.get("/reports/excel")
def excel_day_report(date: str | None = None):
    reconciled = _require_reconciled()
    frame, _bounds, label, latest, stamp = _frame_for_date(reconciled, date)
    if frame is None or frame.empty:
        hint = f" Latest capture in this batch is {latest}." if latest else ""
        raise HTTPException(status_code=400, detail=f"No payments on {label}.{hint}")
    metrics = compute_metrics(frame)
    payload = build_excel_report(frame, date_label=format_day_label(stamp) or label, metrics=metrics)
    file_stamp = stamp or latest or "batch"
    log_audit("report_export", "-", f"Excel day report downloaded ({file_stamp})", "ops_controller")
    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="razorai-{file_stamp}.xlsx"'},
    )


@app.get("/cash/position")
def cash_position():
    reconciled = _require_reconciled()
    return _cash_view(reconciled)


@app.get("/ledgers/sources")
def ledger_sources():
    reconciled = _require_reconciled()
    return build_source_view(reconciled)


@app.get("/tax/lines")
def tax_lines():
    reconciled = _require_reconciled()
    return build_tax_lines(reconciled)


@app.get("/config")
def get_config():
    return public_config()


@app.get("/batch/ingest-report")
def ingest_report():
    return _state["last_ingest"] or {"warnings": ["No file has been ingested in this session."]}


@app.get("/exceptions/{payment_id}/investigate")
def investigate_exception(payment_id: str):
    reconciled = _require_reconciled()
    payload = investigate(reconciled, payment_id, _state["resolutions"])
    if not payload.get("found"):
        raise HTTPException(status_code=404, detail=payload.get("what_happened") or "Not found")
    batch_id = (_state["batch_meta"] or {}).get("batch_id")
    save_investigation(batch_id, payment_id, dump_investigation(payload))
    memory = match_resolution_memory(
        payload.get("related", {}).get("payment") or {"payment_id": payment_id, "mismatch_type": payload.get("mismatch_type")},
        list_resolution_memory(payload.get("mismatch_type")),
        list_controller_rules(),
    )
    for rule in memory.get("matched_rules") or []:
        bump_rule_influence(rule["id"])
    payload["resolution_memory"] = memory
    payload["responsible"] = {
        "conclusion": payload.get("what_happened"),
        "confidence": payload.get("confidence"),
        "evidence": payload.get("evidence_ids"),
        "calculations": payload.get("waterfall"),
        "data_timestamp": payload.get("investigated_at"),
        "recommended_action": payload.get("recommended_action"),
        "unexplained_rupees": (payload.get("waterfall") or {}).get("remaining_rupees"),
    }
    log_audit("investigate", payment_id, payload.get("what_happened") or "investigated", "ops_controller")
    return payload


@app.get("/exceptions/{payment_id}/difference")
def exception_difference(payment_id: str):
    reconciled = _require_reconciled()
    matches = reconciled[reconciled["payment_id"] == payment_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    return explain_difference(matches.iloc[-1].to_dict())


@app.get("/exceptions/{payment_id}/notes")
def exception_notes(payment_id: str):
    return list_analyst_notes(payment_id)


@app.get("/recurring")
def recurring_discrepancies():
    reconciled = _require_reconciled()
    return detect_recurring(reconciled, _state["history_recurrence"])


@app.post("/cash/what-if")
def cash_what_if(req: WhatIfRequest):
    reconciled = _require_reconciled()
    return what_if(
        reconciled,
        delay_settlement_rupees=req.delay_settlement_rupees,
        refund_increase_pct=req.refund_increase_pct,
        drop_unresolved=req.drop_unresolved,
        extra_payout_rupees=req.extra_payout_rupees,
    )


@app.get("/notifications")
def get_notifications(unread_only: bool = False, limit: int = 50):
    return notifications_payload(unread_only=unread_only, limit=limit)


@app.post("/notifications/{notification_id}/read")
def read_notification(notification_id: int):
    item = mark_read(notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    return item


@app.post("/notifications/read-all")
def read_all_notifications():
    return {"marked": mark_all_read()}


@app.get("/withdrawals")
def get_withdrawals(
    q: str = "",
    preset: str = "all",
    start: str | None = None,
    end: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 100,
):
    bounds = resolve_range(preset, start, end, start_time, end_time)
    if bounds.get("inverted"):
        return {"environment": "synthetic", "last": withdrawal_service.last_withdrawal(), "history": []}
    return {
        "environment": "synthetic",
        "last": withdrawal_service.last_withdrawal(),
        "history": withdrawal_service.history(query=q, start=bounds.get("start"), end=bounds.get("end"), limit=limit),
    }


@app.get("/withdrawals/availability")
def withdrawal_availability(as_of: str | None = None):
    reconciled = _require_reconciled()
    try:
        return withdrawal_service.availability(reconciled, as_of)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/withdrawals/preview")
def withdrawal_preview(req: WithdrawRequest):
    reconciled = _require_reconciled()
    try:
        return withdrawal_service.analyze(reconciled, req.amount_rupees, req.as_of)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/withdrawals")
def create_withdrawal(req: WithdrawRequest):
    reconciled = _require_reconciled()
    try:
        result = withdrawal_service.execute(reconciled, req.amount_rupees, req.as_of)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log_audit(
        "withdrawal",
        result["withdrawal"]["withdrawal_id"],
        f"Synthetic withdrawal {result['withdrawal']['requested_rupees']} → net {result['withdrawal']['net_rupees']}",
        "ops_controller",
        previous_state=str(result["analysis"].get("already_withdrawn_rupees")),
        new_state=str(result["availability"].get("already_withdrawn_rupees")),
        actor="finance_ops",
    )
    return result


@app.post("/exceptions/resolve")
def resolve_exception(req: ResolveRequest):
    reconciled = _require_reconciled()
    action = req.action.strip().lower()
    allowed = {
        "apply_fix", "escalate", "waive",
        "acknowledge", "investigate", "assign", "add_note", "reopen", "reject", "approve",
    }
    if action not in allowed:
        raise HTTPException(status_code=400, detail=f"action must be one of {sorted(allowed)}")

    matches = reconciled[reconciled["payment_id"] == req.payment_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Payment {req.payment_id} not found in this batch")

    row = matches.iloc[-1].to_dict()
    mismatch_type = row.get("mismatch_type")
    previous = _state["resolutions"].get(req.payment_id)
    batch_id = (_state["batch_meta"] or {}).get("batch_id")

    if action in {"acknowledge", "investigate", "assign", "add_note", "reopen", "reject"}:
        record = stamp_resolution(req.payment_id, action, mismatch_type or "unknown", req.note, req.actor)
        if action == "reopen":
            _state["resolutions"].pop(req.payment_id, None)
            record = stamp_resolution(req.payment_id, "reopen", mismatch_type or "unknown", req.note, req.actor)
        _state["resolutions"][req.payment_id] = record
        save_analyst_note(
            batch_id, req.payment_id, action, req.note, req.actor,
            (previous or {}).get("workflow_status") or "Open",
            record["workflow_status"],
        )
        log_audit(action, req.payment_id, req.note or record["workflow_status"], "ops_controller")
        return {
            "resolution": record,
            "batch_metrics": _enrich_metrics(compute_metrics(_state["reconciled"])),
            "this_payment": _public_exception(row),
        }

    if action == "approve":
        action = "apply_fix" if suggest(mismatch_type).get("auto_fixable") else "escalate"

    matches = reconciled[reconciled["payment_id"] == req.payment_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Payment {req.payment_id} not found in this batch")

    row = matches.iloc[-1].to_dict()
    mismatch_type = row.get("mismatch_type")
    if row.get("reconciliation_status") != "exception" and action != "waive":
        raise HTTPException(status_code=400, detail="Only open exceptions can be resolved")

    if action == "escalate":
        record = stamp_resolution(req.payment_id, "escalate", mismatch_type or "unknown", req.note)
        _state["resolutions"][req.payment_id] = record
        log_audit("escalate", req.payment_id, req.note or suggest(mismatch_type)["label"], "ops_controller")
        if req.remember:
            _remember_resolution(row, record, req.note)
        return {
            "resolution": record,
            "batch_metrics": _enrich_metrics(compute_metrics(_state["reconciled"])),
            "this_payment": _public_exception(row),
        }

    if action == "apply_fix":
        suggestion = suggest(mismatch_type)
        if not suggestion["auto_fixable"]:
            raise HTTPException(
                status_code=400,
                detail=f"{mismatch_type} cannot be auto-fixed. Escalate it instead.",
            )
        try:
            _state["transactions"] = apply_fix(_state["transactions"], req.payment_id, mismatch_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        resolved_action = "waive" if mismatch_type == "timing_mismatch" else "apply_fix"
    else:
        if mismatch_type == "timing_mismatch":
            _state["transactions"] = apply_fix(_state["transactions"], req.payment_id, mismatch_type)
            resolved_action = "waive"
        else:
            record = stamp_resolution(req.payment_id, "waive", mismatch_type or "unknown", req.note)
            _state["resolutions"][req.payment_id] = record
            log_audit("waive", req.payment_id, req.note or "Accepted without ledger mutation", "ops_controller")
            if req.remember:
                _remember_resolution(row, record, req.note)
            remaining = [item for item in _list_exceptions(include_closed=True) if item["payment_id"] == req.payment_id]
            return {
                "resolution": record,
                "batch_metrics": _enrich_metrics(compute_metrics(_state["reconciled"])),
                "this_payment": remaining[0] if remaining else _public_exception(row),
            }

    _state["reconciled"] = reconcile(_state["transactions"])
    record = stamp_resolution(req.payment_id, resolved_action, mismatch_type or "unknown", req.note)
    _state["resolutions"][req.payment_id] = record
    log_audit(resolved_action, req.payment_id, req.note or suggest(mismatch_type)["label"], "ops_controller")
    if req.remember:
        _remember_resolution(row, record, req.note)

    refreshed = _state["reconciled"][_state["reconciled"]["payment_id"] == req.payment_id]
    this_payment = refreshed.iloc[-1].to_dict() if not refreshed.empty else row
    this_payment["explanation"] = explain(this_payment)
    return {
        "resolution": record,
        "batch_metrics": _enrich_metrics(compute_metrics(_state["reconciled"])),
        "this_payment": {key: json_safe(value) for key, value in this_payment.items()},
    }


@app.post("/books/close")
def close_books():
    """
    Closes one finance-ops loop on the loaded batch:
    1. Reconcile if needed
    2. Auto-apply every deterministic fix
    3. Leave an honest list of exceptions the agent could not resolve
    4. Report match rate, remaining breaks, and cash position
    """
    _require_batch()
    if _state["reconciled"] is None:
        _run_reconciliation()

    initial = _enrich_metrics(compute_metrics(_state["reconciled"]))
    applied = []
    skipped = []

    for payment_id in auto_fixable_ids(_state["reconciled"], _state["resolutions"]):
        row = _state["reconciled"][_state["reconciled"]["payment_id"] == payment_id].iloc[-1]
        mismatch_type = row["mismatch_type"]
        try:
            _state["transactions"] = apply_fix(_state["transactions"], payment_id, mismatch_type)
            resolved_action = "waive" if mismatch_type == "timing_mismatch" else "apply_fix"
            _state["resolutions"][payment_id] = stamp_resolution(
                payment_id, resolved_action, mismatch_type, "Auto-applied while closing the books"
            )
            applied.append({"payment_id": payment_id, "mismatch_type": mismatch_type})
            log_audit(resolved_action, payment_id, f"Auto-fixed {mismatch_type}", "ops_controller")
        except ValueError:
            skipped.append(payment_id)

    _state["reconciled"] = reconcile(_state["transactions"])
    final = _enrich_metrics(compute_metrics(_state["reconciled"]))
    remaining = _list_exceptions()
    log_audit(
        "books_close",
        ",".join(item["payment_id"] for item in applied) or "-",
        f"Auto-resolved {len(applied)}; {len(remaining)} exceptions remain",
        "ops_controller",
    )
    return {
        "initial": initial,
        "auto_resolved": len(applied),
        "resolved": applied,
        "skipped": skipped,
        "final": final,
        "remaining_exceptions": remaining,
        "cash": _cash_view(_state["reconciled"]),
        "tax": build_tax_lines(_state["reconciled"]),
        "sources": build_source_view(_state["reconciled"]),
    }


@app.post("/demo/reset")
def demo_reset():
    """Clears all state and the audit trail."""
    _state["transactions"] = None
    _state["reconciled"] = None
    _state["answer_key"] = None
    _state["resolutions"] = {}
    _state["last_validation"] = None
    _state["batch_meta"] = None
    _state["last_ingest"] = None
    _state["snapshots"] = []
    _state["pending_chat_action"] = None
    _state["last_focus_payment_id"] = None
    _state["razorpay_pending"] = {}
    reset_db()
    return {"status": "reset"}


@app.post("/demo/simulate-payment")
def simulate_payment(req: DemoPaymentRequest):
    """Adds and reconciles a payment from the demo ecommerce flow."""
    if req.amount_rupees <= 0:
        raise HTTPException(status_code=400, detail="amount_rupees must be positive")

    try:
        rows = build_demo_transaction(req.amount_rupees, req.outcome)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _ingest_demo_rows(
        rows,
        outcome=req.outcome,
        items=req.items,
        customer_name=req.customer_name,
        customer_email=req.customer_email,
        payment_method=req.payment_method,
        audit_source="ecommerce_demo",
    )


@app.post("/demo/razorpay/create-order")
def create_razorpay_order(req: RazorpayCreateOrderRequest):
    """Create a Razorpay Test Mode order. Returns order_id and the public key_id only."""
    if req.amount_rupees <= 0:
        raise HTTPException(status_code=400, detail="amount_rupees must be positive")
    if req.outcome not in VALID_OUTCOMES:
        raise HTTPException(status_code=400, detail=f"Unknown outcome '{req.outcome}'")
    if not razorpay_gateway.is_configured():
        raise HTTPException(status_code=503, detail="Razorpay test keys are not configured")

    amount_paise = int(round(req.amount_rupees * 100))
    try:
        order = razorpay_gateway.create_order(amount_paise, notes={"outcome": req.outcome, "demo": "northwind"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not create Razorpay order") from exc

    order_id = str(order.get("id") or "")
    if not order_id:
        raise HTTPException(status_code=502, detail="Razorpay order was missing id")

    _state["razorpay_pending"][order_id] = {
        "outcome": req.outcome,
        "items": req.items or [],
        "customer_name": req.customer_name,
        "customer_email": req.customer_email,
        "payment_method": req.payment_method,
        "amount_paise": amount_paise,
    }
    return {
        "order_id": order_id,
        "key_id": razorpay_gateway.public_key_id(),
        "amount": int(order.get("amount") or amount_paise),
        "currency": order.get("currency") or "INR",
    }


@app.post("/demo/razorpay/verify")
def verify_razorpay_payment(req: RazorpayVerifyRequest):
    """HMAC-verify the Checkout.js callback, fetch the payment, then ingest like simulate-payment."""
    if not razorpay_gateway.is_configured():
        raise HTTPException(status_code=503, detail="Razorpay test keys are not configured")
    if not (req.razorpay_order_id and req.razorpay_payment_id and req.razorpay_signature):
        raise HTTPException(status_code=400, detail="order_id, payment_id and signature are required")
    if not razorpay_gateway.verify_payment_signature(
        req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature
    ):
        raise HTTPException(status_code=400, detail="Invalid Razorpay payment signature")

    try:
        fetched = razorpay_gateway.fetch_payment(req.razorpay_payment_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not fetch Razorpay payment") from exc

    if str(fetched.get("order_id") or "") != req.razorpay_order_id:
        raise HTTPException(status_code=400, detail="Payment does not belong to this order")
    if str(fetched.get("status") or "") not in {"captured", "authorized"}:
        raise HTTPException(status_code=400, detail="Payment is not captured")

    pending = _state["razorpay_pending"].pop(req.razorpay_order_id, None)
    if pending is None:
        try:
            order = razorpay_gateway.fetch_order(req.razorpay_order_id)
            notes = order.get("notes") or {}
            pending = {"outcome": notes.get("outcome") or "clean"}
        except Exception:
            pending = {"outcome": "clean"}

    outcome = pending.get("outcome") or "clean"
    try:
        rows = map_razorpay_payment(fetched, outcome)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _ingest_demo_rows(
        rows,
        outcome=outcome,
        items=pending.get("items") or [],
        customer_name=pending.get("customer_name"),
        customer_email=pending.get("customer_email"),
        payment_method=pending.get("payment_method"),
        audit_source="razorpay_test_api",
    )


@app.get("/")
def root():
    return {
        "service": "Razor-AI Finance Controller API",
        "docs": "/docs",
        "status": "ok",
        "loop": "reconcile → investigate → explain → resolve → audit → predict",
        "config": public_config(),
    }


@app.get("/demo/orders")
def demo_orders():
    return {"orders": [_public_store_order(row) for row in list_store_orders()]}


@app.post("/demo/refund")
def demo_refund(req: RefundRequest):
    _require_batch()
    order = get_store_order(req.payment_id)
    try:
        next_transactions, applied = apply_refund(_state["transactions"], req.payment_id, req.amount_rupees)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not req.confirm:
        return {
            "requires_confirmation": True,
            "preview": applied,
            "order": _public_store_order(order) if order else None,
            "message": (
                f"Refund ₹{applied['applied_rupees']:,.2f} on {applied['payment_id']}. "
                "Confirm to post it through reconciliation, cash, GST and notifications."
            ),
        }
    _state["transactions"] = next_transactions

    _state["reconciled"] = reconcile(_state["transactions"])
    if _state["batch_meta"]:
        _state["batch_meta"]["record_count"] = int(len(_state["transactions"]))
    new_status = applied["status"]
    if order:
        update_store_order_refund(req.payment_id, applied["refund_amount_paise"], new_status)
    else:
        row = _state["reconciled"][_state["reconciled"]["payment_id"] == req.payment_id].iloc[-1].to_dict()
        insert_store_order(
            payment_id=req.payment_id,
            order_id=str(row.get("order_id") or ""),
            amount_paise=int(float(row.get("amount") or 0)),
            status=new_status,
            outcome="refund",
            items_json="[]",
            customer_name=None,
            customer_email=None,
            payment_method=str(row.get("payment_method") or ""),
        )
        update_store_order_refund(req.payment_id, applied["refund_amount_paise"], new_status)

    refreshed = _state["reconciled"][_state["reconciled"]["payment_id"] == req.payment_id]
    this_payment = refreshed.iloc[-1].to_dict() if not refreshed.empty else {}
    flagged = notify_new_exceptions(
        [{**row.to_dict(), "explanation": explain(row.to_dict())} for _, row in refreshed.iterrows()],
        "ecommerce_demo",
    )
    refund_note = notify_refund(
        req.payment_id,
        applied["applied_paise"],
        f"Refund of ₹{applied['applied_rupees']:,.2f} initiated on {req.payment_id}.",
        "ecommerce_demo",
    )
    log_audit(
        "refund_initiated",
        req.payment_id,
        f"Refund {applied['applied_rupees']} posted. Remaining ₹{paise_to_rupees(applied['remaining_paise'])}.",
        "ecommerce_demo",
        previous_state=str(order.get("refunded_paise") if order else 0),
        new_state=str(applied["refund_amount_paise"]),
        actor="store_customer",
    )
    _capture_snapshot()
    return {
        "refund": applied,
        "this_payment": {key: json_safe(value) for key, value in this_payment.items()},
        "order": _public_store_order(get_store_order(req.payment_id) or {}),
        "batch_metrics": _enrich_metrics(compute_metrics(_state["reconciled"])),
        "cash": _cash_view(_state["reconciled"]),
        "notifications": [item for item in [refund_note, *flagged] if item],
    }


@app.get("/controller/overview")
def controller_overview(versus: str = "yesterday"):
    return _controller_pack(versus)


@app.get("/controller/briefing")
def controller_briefing():
    if _state["reconciled"] is None:
        return build_briefing(None, None, None, {}, 0.0, [], [], [])
    return _controller_pack()["briefing"]


@app.get("/controller/what-changed")
def controller_what_changed(versus: str = "yesterday"):
    if _state["reconciled"] is None:
        return compare_periods(None, {}, 0.0, 0.0, [], versus)
    reconciled = _state["reconciled"]
    cash = _cash_view(reconciled)
    return compare_periods(
        reconciled, _state["resolutions"], float(cash.get("withdrawn_rupees") or 0),
        cash.get("available_rupees") or 0, _loaded_snapshots(), versus,
        current_batch_id=(_state["batch_meta"] or {}).get("batch_id"),
    )


@app.get("/controller/clusters")
def controller_clusters():
    return cluster_exceptions(_require_reconciled(), _state["resolutions"])


@app.get("/controller/action-queue")
def controller_action_queue():
    return _controller_pack()["action_queue"]


@app.get("/controller/health")
def controller_health():
    return _controller_pack()["health"]


@app.get("/controller/anomalies")
def controller_anomalies():
    return detect_anomalies(_require_reconciled())


@app.get("/controller/refunds")
def controller_refunds():
    return refund_intelligence(_require_reconciled())


@app.get("/controller/aging")
def controller_aging():
    return exception_aging(_require_reconciled(), _state["resolutions"])


@app.get("/controller/performance")
def controller_performance():
    metrics = _enrich_metrics(compute_metrics(_require_reconciled()))
    return performance_metrics(metrics, _state["resolutions"], _state["last_validation"])


@app.get("/controller/merchants")
def controller_merchants():
    return merchant_profiles(_require_reconciled(), _state["resolutions"])


@app.get("/cash/why")
def cash_why():
    reconciled = _require_reconciled()
    cash = _cash_view(reconciled)
    return cash_gap(reconciled, cash, float(cash.get("withdrawn_rupees") or 0))


@app.get("/search")
def finance_search(q: str = ""):
    reconciled = _require_reconciled()
    tax = build_tax_lines(reconciled)
    withdrawals = withdrawal_service.history(limit=50)
    audit = get_audit_trail(limit=50, q=q or None)
    return search_finance(reconciled, q, tax, withdrawals, audit, _state["resolutions"])


@app.post("/search")
def finance_search_post(req: SearchRequest):
    return finance_search(req.query)


@app.get("/records/{payment_id}/timeline")
def payment_timeline(payment_id: str):
    reconciled = _require_reconciled()
    matches = reconciled[reconciled["payment_id"] == payment_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    row = matches.iloc[-1].to_dict()
    inv = get_investigation(payment_id)
    investigation = None
    if inv:
        try:
            investigation = json.loads(inv["payload"])
        except (TypeError, json.JSONDecodeError):
            investigation = {"investigated_at": inv.get("timestamp")}
    audit = get_audit_trail(limit=200, q=payment_id)
    return {
        "payment_id": payment_id,
        "events": record_timeline(row, audit, investigation, _state["resolutions"].get(payment_id)),
    }


@app.post("/exceptions/batch-resolve")
def batch_resolve(req: BatchResolveRequest):
    reconciled = _require_reconciled()
    payment_ids = list(req.payment_ids or [])
    cluster = None
    if req.cluster_id:
        clusters = cluster_exceptions(reconciled, _state["resolutions"])
        cluster = next((item for item in clusters if item["cluster_id"] == req.cluster_id), None)
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")
        payment_ids = list(cluster["payment_ids"])
    if not payment_ids:
        raise HTTPException(status_code=400, detail="payment_ids or cluster_id required")

    members = []
    skipped_preview = []
    impact = 0.0
    for pid in payment_ids:
        matches = reconciled[reconciled["payment_id"] == pid]
        if matches.empty:
            skipped_preview.append({"payment_id": pid, "reason": "not in batch"})
            continue
        row = matches.iloc[-1].to_dict()
        mismatch = row.get("mismatch_type")
        suggestion = suggest(mismatch)
        if row.get("reconciliation_status") != "exception":
            skipped_preview.append({"payment_id": pid, "reason": "not an open exception"})
            continue
        if req.action == "apply_fix" and not suggestion.get("auto_fixable"):
            skipped_preview.append({"payment_id": pid, "reason": f"{mismatch} cannot be auto-fixed"})
            continue
        impact += float(row.get("amount") or 0)
        members.append(_public_exception(row))

    preview = {
        "requires_confirmation": True,
        "action": req.action,
        "count": len(members),
        "skipped": skipped_preview,
        "total_amount_rupees": paise_to_rupees(impact),
        "root_cause": (cluster or {}).get("root_cause"),
        "ai_confidence": ((cluster or {}).get("root_cause") or {}).get("confidence"),
        "expected_effect": (
            f"Re-run reconciliation on {len(members)} validated records. "
            "Rows that cannot be auto-fixed stay open."
        ),
        "records": members[:40],
        "payment_ids": [item["payment_id"] for item in members],
    }
    if not req.confirm:
        return preview

    applied = []
    skipped = list(skipped_preview)
    for item in members:
        pid = item["payment_id"]
        try:
            result = resolve_exception(ResolveRequest(
                payment_id=pid,
                action=req.action,
                note=req.note or (f"Batch resolve {req.cluster_id}" if req.cluster_id else "Batch resolve"),
                actor=req.actor,
                remember=req.remember,
            ))
            applied.append({"payment_id": pid, "resolution": result.get("resolution")})
        except HTTPException as exc:
            skipped.append({"payment_id": pid, "reason": exc.detail})
    log_audit(
        "batch_resolve",
        ",".join(item["payment_id"] for item in applied) or "-",
        f"Batch {req.action}: {len(applied)} applied, {len(skipped)} skipped",
        "ops_controller",
        actor=req.actor,
    )
    _capture_snapshot()
    return {
        "confirmed": True,
        "applied": applied,
        "skipped": skipped,
        "batch_metrics": _enrich_metrics(compute_metrics(_state["reconciled"])) if _state["reconciled"] is not None else None,
        "remaining_exceptions": _list_exceptions(),
    }


@app.get("/controller/rules")
def get_rules():
    return {"rules": list_controller_rules()}


@app.post("/controller/rules")
def create_rule(req: RuleCreateRequest):
    if req.origin != "human":
        raise HTTPException(status_code=400, detail="Only human-created rules can be stored as financial guidance")
    rule = insert_controller_rule(
        title=req.title,
        mismatch_type=req.mismatch_type,
        payment_method=req.payment_method,
        merchant_key=req.merchant_key,
        resolution_category=req.resolution_category,
        guidance=req.guidance,
        origin="human",
        actor=req.actor,
    )
    log_audit("controller_rule", str(rule["id"]), req.title, "ops_controller", actor=req.actor)
    return rule


@app.patch("/controller/rules/{rule_id}")
def patch_rule(rule_id: int, req: RuleUpdateRequest):
    if not get_controller_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    payload = req.model_dump(exclude_unset=True)
    if "enabled" in payload and payload["enabled"] is not None:
        payload["enabled"] = 1 if payload["enabled"] else 0
    updated = update_controller_rule(rule_id, **payload)
    log_audit("controller_rule_update", str(rule_id), json.dumps(payload), "ops_controller")
    return updated


@app.delete("/controller/rules/{rule_id}")
def remove_rule(rule_id: int):
    if not delete_controller_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    log_audit("controller_rule_delete", str(rule_id), "deleted", "ops_controller")
    return {"deleted": True}


@app.get("/controller/memory")
def get_memory(mismatch_type: str | None = None):
    return {"memory": list_resolution_memory(mismatch_type)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
