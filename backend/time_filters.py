"""Deterministic datetime range parsing for payments, exceptions, and audit."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import pandas as pd

PRESETS = ("all", "today", "yesterday", "last_7_days", "last_30_days", "custom")

MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_MONTH_PATTERN = "|".join(sorted(MONTH_NAMES, key=len, reverse=True))
_ISO_RE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
_DMY_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b")
_DAY_MONTH_RE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_PATTERN})(?:[,\s]+(20\d{{2}}))?\b",
    re.I,
)
_MONTH_DAY_RE = re.compile(
    rf"\b({_MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(20\d{{2}}))?\b",
    re.I,
)


def format_day_label(stamp: str | None) -> str:
    """Turn YYYY-MM-DD into '14 Aug 2026'."""
    if not stamp:
        return ""
    raw = str(stamp).strip()[:10]
    try:
        day = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    return f"{day.day} {day.strftime('%b %Y')}"


def _safe_iso(year: int, month: int, day: int) -> str | None:
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_mentioned_date(text: str, default_year: int | None = None) -> str | None:
    """
    Extract a calendar day from prose such as 'August 14', '14 Aug 2026',
    or '2026-08-14'. Does not treat 'today' as the wall-clock date so a
    historical demo batch stays in scope.
    """
    if not text:
        return None
    year = default_year or datetime.now().year

    iso = _ISO_RE.search(text)
    if iso:
        return _safe_iso(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))

    dmy = _DMY_RE.search(text)
    if dmy:
        day_n, month_n, year_n = int(dmy.group(1)), int(dmy.group(2)), int(dmy.group(3))
        if month_n > 12 and day_n <= 12:
            day_n, month_n = month_n, day_n
        return _safe_iso(year_n, month_n, day_n)

    named = _DAY_MONTH_RE.search(text)
    if named:
        year_n = int(named.group(3)) if named.group(3) else year
        return _safe_iso(year_n, MONTH_NAMES[named.group(2).lower()], int(named.group(1)))

    named_md = _MONTH_DAY_RE.search(text)
    if named_md:
        year_n = int(named_md.group(3)) if named_md.group(3) else year
        return _safe_iso(year_n, MONTH_NAMES[named_md.group(1).lower()], int(named_md.group(2)))

    return None


def parse_clock(value: str | None, fallback: str) -> tuple[int, int, int]:
    raw = (value or fallback).strip()
    parts = raw.split(":")
    hour = int(parts[0]) if parts and parts[0].isdigit() else 0
    minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    second = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    hour = min(23, max(0, hour))
    minute = min(59, max(0, minute))
    second = min(59, max(0, second))
    return hour, minute, second


def combine_date_time(date_str: str | None, time_str: str | None, end: bool = False) -> datetime | None:
    if not date_str:
        return None
    try:
        day = datetime.fromisoformat(date_str[:10])
    except ValueError:
        return None
    hour, minute, second = parse_clock(time_str, "23:59:59" if end else "00:00:00")
    if end and not time_str:
        hour, minute, second = 23, 59, 59
    return day.replace(hour=hour, minute=minute, second=second)


def resolve_range(
    preset: str | None = "all",
    start: str | None = None,
    end: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now()
    preset = (preset or "all").strip().lower()
    if preset not in PRESETS:
        preset = "all"

    range_start = None
    range_end = None
    warning = None

    if preset == "today":
        range_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        range_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    elif preset == "yesterday":
        day = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        range_start = day
        range_end = day.replace(hour=23, minute=59, second=59)
    elif preset == "last_7_days":
        range_start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        range_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    elif preset == "last_30_days":
        range_start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        range_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    elif preset == "custom":
        range_start = combine_date_time(start, start_time, end=False)
        range_end = combine_date_time(end, end_time, end=True)
        if start and not range_start:
            warning = "Start date was invalid and was ignored."
        if end and not range_end:
            warning = "End date was invalid and was ignored."
        if range_start and range_end and range_start > range_end:
            warning = "Start is after end. No records match this range."
    # preset "all" leaves both bounds None

    return {
        "preset": preset,
        "start": range_start.isoformat() if range_start else None,
        "end": range_end.isoformat() if range_end else None,
        "start_dt": range_start,
        "end_dt": range_end,
        "inverted": bool(range_start and range_end and range_start > range_end),
        "warning": warning,
    }


def apply_range(df: pd.DataFrame, column: str, bounds: dict) -> pd.DataFrame:
    if df is None or df.empty or column not in df.columns:
        return df.iloc[0:0] if df is not None else pd.DataFrame()
    if bounds.get("inverted"):
        return df.iloc[0:0]
    start = bounds.get("start_dt")
    end = bounds.get("end_dt")
    if start is None and end is None:
        return df
    stamps = pd.to_datetime(df[column], errors="coerce")
    mask = stamps.notna()
    if start is not None:
        mask &= stamps >= pd.Timestamp(start)
    if end is not None:
        mask &= stamps <= pd.Timestamp(end)
    return df.loc[mask]
