"""Persistent notifications for newly flagged payments. No duplicates on reload."""

from __future__ import annotations

from database import (
    insert_notification,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)


def notify_refund(payment_id: str, amount_paise: int, reason: str, source: str = "ecommerce_demo") -> dict | None:
    """Always attempt a refund-initiated notification; unique per payment + attempt."""
    for attempt in range(1, 12):
        mismatch_type = "refund_initiated" if attempt == 1 else f"refund_initiated_{attempt}"
        record = insert_notification(
            payment_id=payment_id,
            exception_id=f"refund_{payment_id}_{attempt}",
            amount_paise=int(amount_paise or 0),
            mismatch_type=mismatch_type,
            priority="Medium",
            reason=reason,
            source=source,
        )
        if record:
            return record
    return None


def notify_payment_captured(row: dict, source: str = "ecommerce_demo") -> dict | None:
    """Notify a live checkout that matched — not used for bulk batch loads."""
    payment_id = str(row.get("payment_id") or "")
    if not payment_id:
        return None
    return insert_notification(
        payment_id=payment_id,
        exception_id=f"pay_{payment_id}",
        amount_paise=int(float(row.get("amount") or 0)),
        mismatch_type="payment_captured",
        priority="Low",
        reason=f"Payment {payment_id} captured and matched into the live batch.",
        source=source,
    )


def notify_new_exceptions(rows: list[dict], source: str = "rule_engine") -> list[dict]:
    created = []
    for row in rows:
        if row.get("reconciliation_status") != "exception":
            continue
        payment_id = str(row.get("payment_id") or "")
        if not payment_id:
            continue
        record = insert_notification(
            payment_id=payment_id,
            exception_id=str(row.get("exception_id") or f"exc_{payment_id}"),
            amount_paise=int(float(row.get("amount") or 0)),
            mismatch_type=str(row.get("mismatch_type") or "unclassified_discrepancy"),
            priority=str(row.get("priority") or "Low"),
            reason=str(row.get("explanation") or row.get("mismatch_type") or "Flagged by reconciliation"),
            source=source,
        )
        if record:
            created.append(record)
    return created


def notifications_payload(unread_only: bool = False, limit: int = 50) -> dict:
    items = list_notifications(unread_only=unread_only, limit=limit)
    unread = sum(1 for item in items if not item.get("read"))
    if unread_only:
        unread = len(items)
    else:
        unread = sum(1 for item in list_notifications(unread_only=True, limit=500))
    return {"notifications": items, "unread": unread}


def mark_read(notification_id: int) -> dict | None:
    return mark_notification_read(notification_id)


def mark_all_read() -> int:
    return mark_all_notifications_read()
