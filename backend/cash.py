"""
Cash position and a 7-day forward settlement forecast.

Razorpay merchants typically see captured money as "in transit" until T+2
(or T+7 in edge cases). This module turns a reconciled batch into the two
numbers a finance controller actually needs: cash already in the bank, and
cash that should arrive over the next week — minus amounts trapped in
unresolved exceptions.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from config import now_ist
from serialize import json_safe, paise_to_rupees


def _as_timestamp(value, fallback: pd.Timestamp) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return fallback
    return ts


def compute_cash_position(reconciled: pd.DataFrame, as_of: datetime | None = None) -> dict:
    """
    Returns available cash, in-transit settlements, exception-blocked amounts,
    and a 7-day daily forecast. All money fields are rupees.
    """
    as_of = as_of or now_ist()
    as_of_ts = pd.Timestamp(as_of)

    if reconciled is None or reconciled.empty:
        return {
            "as_of": as_of_ts.isoformat(),
            "available_rupees": 0.0,
            "in_transit_rupees": 0.0,
            "blocked_rupees": 0.0,
            "expected_7d_rupees": 0.0,
            "net_7d_rupees": 0.0,
            "forecast": [],
            "notes": "No reconciled batch is loaded.",
        }

    df = reconciled.copy()
    df["settled_at"] = pd.to_datetime(df["settled_at"], errors="coerce")
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["settlement_amount"] = pd.to_numeric(df["settlement_amount"], errors="coerce").fillna(0)
    df["expected_settlement"] = pd.to_numeric(df.get("expected_settlement"), errors="coerce")

    matched = df["reconciliation_status"] == "matched"
    exception = df["reconciliation_status"] == "exception"

    already_settled = matched & df["settled_at"].notna() & (df["settled_at"] <= as_of_ts)
    still_in_transit = matched & (~already_settled)

    available = float(df.loc[already_settled, "settlement_amount"].sum())
    in_transit = float(df.loc[still_in_transit, "settlement_amount"].sum())

    blocked_series = df.loc[exception, "expected_settlement"]
    blocked_fallback = df.loc[exception, "amount"].fillna(0) - df.loc[exception, "fee"].fillna(0) - df.loc[exception, "tax"].fillna(0) - df.loc[exception, "refund_amount"].fillna(0)
    blocked = float(blocked_series.fillna(blocked_fallback).fillna(0).sum())

    horizon = [as_of_ts.normalize() + timedelta(days=i) for i in range(7)]
    forecast = []
    expected_7d = 0.0

    for day in horizon:
        day_end = day + timedelta(days=1)
        due = still_in_transit & df["settled_at"].notna() & (df["settled_at"] >= day) & (df["settled_at"] < day_end)
        at_risk = exception & df["settled_at"].notna() & (df["settled_at"] >= day) & (df["settled_at"] < day_end)
        inflow = float(df.loc[due, "settlement_amount"].sum())
        risk = float(df.loc[at_risk, "settlement_amount"].fillna(0).sum())
        expected_7d += inflow
        forecast.append({
            "date": day.date().isoformat(),
            "label": day.strftime("%a %d %b"),
            "expected_inflow_rupees": paise_to_rupees(inflow),
            "blocked_rupees": paise_to_rupees(risk),
            "net_rupees": paise_to_rupees(inflow),
            "payments_due": int(due.sum()),
            "exceptions_due": int(at_risk.sum()),
        })

    return {
        "as_of": as_of_ts.isoformat(),
        "available_rupees": paise_to_rupees(available),
        "in_transit_rupees": paise_to_rupees(in_transit),
        "blocked_rupees": paise_to_rupees(blocked),
        "expected_7d_rupees": paise_to_rupees(expected_7d),
        "net_7d_rupees": paise_to_rupees(expected_7d),
        "matched_count": int(matched.sum()),
        "exception_count": int(exception.sum()),
        "forecast": forecast,
        "horizon": {
            "next_day_rupees": forecast[0]["expected_inflow_rupees"] if forecast else 0.0,
            "next_3d_rupees": round(sum(day["expected_inflow_rupees"] for day in forecast[:3]), 2) if forecast else 0.0,
            "next_7d_rupees": paise_to_rupees(expected_7d),
        },
        "confidence": round(max(0.35, 1 - (blocked / (available + in_transit + blocked + 1))), 4),
        "unresolved_settlement_rupees": paise_to_rupees(blocked),
        "assumptions": [
            "Matched rows with settled_at in the past are treated as available cash.",
            "Matched rows not yet dated as settled are in transit (T+2 and later).",
            "Next 7 days is only the in-transit slice with settled_at inside the coming week.",
            "Exception amounts are excluded from projected inflows until resolved.",
            "No upcoming payouts or known expenses were supplied, so they are assumed ₹0.",
        ],
        "notes": (
            "Available cash is matched settlements already past settled_at. "
            "In-transit is all matched money not yet received. "
            "Next 7 days is only in-transit dated inside the coming week, so it can be smaller. "
            "Blocked cash sits in unresolved exceptions and is excluded from the 7-day net."
        ),
    }


def cash_alerts(position: dict) -> list[dict]:
    alerts = []
    blocked = float(position.get("blocked_rupees") or 0)
    available = float(position.get("available_rupees") or 0)
    expected_7d = float(position.get("expected_7d_rupees") or 0)
    if blocked > 0:
        alerts.append({
            "severity": "high" if blocked > 50000 else "medium",
            "code": "unresolved_settlements",
            "message": f"₹{blocked:,.2f} of expected settlements remain unresolved.",
            "why": "Open exceptions are excluded from available and 7-day net cash.",
        })
    if expected_7d == 0 and blocked > 0:
        alerts.append({
            "severity": "medium",
            "code": "no_inflow",
            "message": "No matched inflows are dated in the next 7 days.",
            "why": "Either settlements are already in the past, or remaining credits are blocked.",
        })
    if blocked > available and available > 0:
        alerts.append({
            "severity": "high",
            "code": "shortfall_risk",
            "message": "Potential cash shortfall: blocked exception amount exceeds available cash.",
            "why": f"Available ₹{available:,.2f} vs blocked ₹{blocked:,.2f}.",
        })
    return alerts


def what_if(
    reconciled: pd.DataFrame,
    delay_settlement_rupees: float = 0,
    refund_increase_pct: float = 0,
    drop_unresolved: bool = False,
    extra_payout_rupees: float = 0,
) -> dict:
    """
    Recalculate cash deterministically under a scenario. Does not mutate the batch.

    Projected operational cash = available + in-transit.
    The 7-day forecast is a slice of in-transit, not an extra add-on.
    """
    base = compute_cash_position(reconciled)
    available = base["available_rupees"]
    in_transit = base["in_transit_rupees"]
    blocked = base["blocked_rupees"]
    expected_7d = base["expected_7d_rupees"]

    delayed = max(0.0, float(delay_settlement_rupees or 0))
    extra_payout = max(0.0, float(extra_payout_rupees or 0))
    refund_hit = in_transit * max(0.0, float(refund_increase_pct or 0)) / 100.0

    applied_delay = min(delayed, in_transit)
    scenario_in_transit = max(0.0, in_transit - applied_delay - refund_hit)
    scenario_7d = max(0.0, expected_7d - min(applied_delay, expected_7d) - refund_hit)
    operational_base = available + in_transit
    projected = available + scenario_in_transit - extra_payout

    notes = []
    if delayed > in_transit:
        notes.append(
            f"Requested delay of ₹{delayed:,.2f} exceeds in-transit ₹{in_transit:,.2f}. "
            "Only known unmatched settlements can be delayed."
        )
    if drop_unresolved:
        notes.append(
            f"Unresolved ₹{blocked:,.2f} was never in operational projected cash. "
            "Treating it as not received does not reduce available + in-transit; it remains excluded."
        )
    if not notes:
        notes.append("Recalculated from the loaded batch. No invented future inflows.")

    return {
        "base": base,
        "scenario": {
            "delay_settlement_rupees": delayed,
            "refund_increase_pct": refund_increase_pct,
            "drop_unresolved": drop_unresolved,
            "extra_payout_rupees": extra_payout,
        },
        "available_rupees": round(available, 2),
        "in_transit_rupees": round(scenario_in_transit, 2),
        "blocked_rupees": round(0.0 if drop_unresolved else blocked, 2),
        "expected_7d_rupees": round(scenario_7d, 2),
        "projected_cash_rupees": round(projected, 2),
        "delta_vs_base_rupees": round(projected - operational_base, 2),
        "hoped_if_exceptions_clear_rupees": round(operational_base + blocked, 2),
        "explanation": (
            f"Delayed ₹{applied_delay:,.2f} of in-transit credit, "
            f"refunds +{refund_increase_pct}% (₹{refund_hit:,.2f}), "
            f"{'unresolved credit stays excluded' if drop_unresolved else 'unresolved still blocked'}, "
            f"extra payout ₹{extra_payout:,.2f}. " + " ".join(notes)
        ),
    }


def row_to_public(row: dict) -> dict:
    return {key: json_safe(value) for key, value in row.items()}
