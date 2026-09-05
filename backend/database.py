"""
SQLite persistence for audit, investigations, notifications, and withdrawals.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from datetime import datetime, timezone

from config import now_ist

DB_PATH = "razorai.db"
_SCHEMA_READY = False
_BUILDING_SCHEMA = False


def get_db() -> sqlite3.Connection:
    global _SCHEMA_READY, _BUILDING_SCHEMA
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
    except sqlite3.OperationalError:
        pass
    if _BUILDING_SCHEMA:
        return conn
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_trail'"
    ).fetchone()
    if row:
        _SCHEMA_READY = True
        return conn
    conn.close()
    _BUILDING_SCHEMA = True
    try:
        init_db()
    finally:
        _BUILDING_SCHEMA = False
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn, table: str, column: str, ddl: str):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db():
    global _SCHEMA_READY
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action_type TEXT NOT NULL,
            record_ids TEXT,
            details TEXT,
            source TEXT NOT NULL
        )
    """)
    _ensure_column(conn, "audit_trail", "actor", "TEXT")
    _ensure_column(conn, "audit_trail", "previous_state", "TEXT")
    _ensure_column(conn, "audit_trail", "new_state", "TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investigations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            batch_id TEXT,
            payment_id TEXT NOT NULL,
            payload TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyst_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            batch_id TEXT,
            payment_id TEXT,
            action TEXT NOT NULL,
            note TEXT,
            actor TEXT,
            previous_state TEXT,
            new_state TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            payment_id TEXT NOT NULL,
            exception_id TEXT,
            amount_paise INTEGER,
            mismatch_type TEXT NOT NULL,
            priority TEXT,
            reason TEXT,
            read INTEGER NOT NULL DEFAULT 0,
            source TEXT,
            UNIQUE(payment_id, mismatch_type)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            withdrawal_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            as_of TEXT NOT NULL,
            requested_paise INTEGER NOT NULL,
            fee_paise INTEGER NOT NULL,
            tax_paise INTEGER NOT NULL,
            refund_paise INTEGER NOT NULL,
            adjustment_paise INTEGER NOT NULL,
            net_paise INTEGER NOT NULL,
            status TEXT NOT NULL,
            environment TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS store_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT NOT NULL UNIQUE,
            order_id TEXT,
            created_at TEXT NOT NULL,
            amount_paise INTEGER NOT NULL,
            refunded_paise INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            outcome TEXT,
            items_json TEXT,
            customer_name TEXT,
            customer_email TEXT,
            payment_method TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metric_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            batch_id TEXT,
            payload TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resolution_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            payment_id TEXT,
            mismatch_type TEXT NOT NULL,
            root_cause TEXT,
            resolution_category TEXT,
            payment_method TEXT,
            merchant_key TEXT,
            human_decision TEXT,
            evidence TEXT,
            amount_paise INTEGER,
            actor TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS controller_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            title TEXT NOT NULL,
            mismatch_type TEXT,
            payment_method TEXT,
            merchant_key TEXT,
            resolution_category TEXT,
            guidance TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            origin TEXT NOT NULL DEFAULT 'human',
            influence_count INTEGER NOT NULL DEFAULT 0,
            actor TEXT
        )
    """)
    conn.commit()
    conn.close()
    _SCHEMA_READY = True


def ensure_db():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        conn = get_db()
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_trail'"
        ).fetchone()
        conn.close()
        if row:
            return
        _SCHEMA_READY = False
    init_db()


def log_audit(action_type: str, record_ids, details: str, source: str, previous_state: str | None = None, new_state: str | None = None, actor: str | None = None):
    ensure_db()
    conn = get_db()
    conn.execute(
        """INSERT INTO audit_trail
           (timestamp, action_type, record_ids, details, source, actor, previous_state, new_state)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            action_type,
            str(record_ids),
            details,
            source,
            actor,
            previous_state,
            new_state,
        ),
    )
    conn.commit()
    conn.close()


def get_audit_trail(limit: int = 100, start: str | None = None, end: str | None = None, action_type: str | None = None, source: str | None = None, q: str | None = None):
    ensure_db()
    conn = get_db()
    clauses = ["1=1"]
    params: list = []
    if start:
        clauses.append("timestamp >= ?")
        params.append(start)
    if end:
        clauses.append("timestamp <= ?")
        params.append(end)
    if action_type and action_type != "all":
        clauses.append("action_type = ?")
        params.append(action_type)
    if source and source != "all":
        if source == "ai":
            clauses.append("source IN ('gemini_api','ai')")
        elif source == "human":
            clauses.append("source IN ('ops_controller','ecommerce_demo','finance_ops')")
        else:
            clauses.append("source = ?")
            params.append(source)
    if q:
        clauses.append("(record_ids LIKE ? OR details LIKE ? OR action_type LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM audit_trail WHERE {' AND '.join(clauses)} ORDER BY timestamp DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reset_db():
    global _SCHEMA_READY
    last_error = None
    for attempt in range(8):
        try:
            conn = get_db()
            for table in (
                "audit_trail", "investigations", "analyst_notes",
                "notifications", "withdrawals", "transactions", "reconciled",
                "store_orders", "metric_snapshots", "resolution_memory", "controller_rules",
            ):
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
            conn.close()
            _SCHEMA_READY = False
            init_db()
            return
        except sqlite3.OperationalError as exc:
            last_error = exc
            if "locked" not in str(exc).lower():
                raise
            time.sleep(0.25 * (attempt + 1))
    if last_error:
        raise last_error


def save_investigation(batch_id: str | None, payment_id: str, payload: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO investigations (timestamp, batch_id, payment_id, payload) VALUES (?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), batch_id, payment_id, payload),
    )
    conn.commit()
    conn.close()


def get_investigation(payment_id: str):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM investigations WHERE payment_id = ? ORDER BY id DESC LIMIT 1",
        (payment_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_analyst_note(batch_id, payment_id, action, note, actor, previous_state, new_state):
    conn = get_db()
    conn.execute(
        """INSERT INTO analyst_notes
           (timestamp, batch_id, payment_id, action, note, actor, previous_state, new_state)
           VALUES (?,?,?,?,?,?,?,?)""",
        (datetime.now(timezone.utc).isoformat(), batch_id, payment_id, action, note, actor, previous_state, new_state),
    )
    conn.commit()
    conn.close()


def list_analyst_notes(payment_id: str | None = None, limit: int = 50):
    conn = get_db()
    if payment_id:
        rows = conn.execute(
            "SELECT * FROM analyst_notes WHERE payment_id = ? ORDER BY id DESC LIMIT ?",
            (payment_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM analyst_notes ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _public_notification(row: dict) -> dict:
    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "payment_id": row["payment_id"],
        "exception_id": row["exception_id"],
        "amount_paise": row["amount_paise"],
        "mismatch_type": row["mismatch_type"],
        "priority": row["priority"],
        "reason": row["reason"],
        "read": bool(row["read"]),
        "source": row["source"],
    }


def insert_notification(payment_id, exception_id, amount_paise, mismatch_type, priority, reason, source):
    conn = get_db()
    cursor = conn.execute(
        """INSERT OR IGNORE INTO notifications
           (timestamp, payment_id, exception_id, amount_paise, mismatch_type, priority, reason, read, source)
           VALUES (?,?,?,?,?,?,?,0,?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            payment_id,
            exception_id,
            amount_paise,
            mismatch_type,
            priority,
            reason,
            source,
        ),
    )
    conn.commit()
    if cursor.rowcount != 1:
        conn.close()
        return None
    row = conn.execute("SELECT * FROM notifications WHERE id = ?", (cursor.lastrowid,)).fetchone()
    conn.close()
    return _public_notification(dict(row)) if row else None


def list_notifications(unread_only: bool = False, limit: int = 50):
    conn = get_db()
    if unread_only:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE read = 0 ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM notifications ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [_public_notification(dict(r)) for r in rows]


def mark_notification_read(notification_id: int):
    conn = get_db()
    conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    row = conn.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
    conn.close()
    return _public_notification(dict(row)) if row else None


def mark_all_notifications_read() -> int:
    conn = get_db()
    cursor = conn.execute("UPDATE notifications SET read = 1 WHERE read = 0")
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return int(count or 0)


def clear_notifications():
    conn = get_db()
    conn.execute("DELETE FROM notifications")
    conn.commit()
    conn.close()


def _public_withdrawal(row: dict) -> dict:
    from serialize import paise_to_rupees
    return {
        "id": row["id"],
        "withdrawal_id": row["withdrawal_id"],
        "created_at": row["created_at"],
        "as_of": row["as_of"],
        "requested_rupees": paise_to_rupees(row["requested_paise"]),
        "fee_rupees": paise_to_rupees(row["fee_paise"]),
        "tax_rupees": paise_to_rupees(row["tax_paise"]),
        "refund_rupees": paise_to_rupees(row["refund_paise"]),
        "adjustment_rupees": paise_to_rupees(row["adjustment_paise"]),
        "net_rupees": paise_to_rupees(row["net_paise"]),
        "status": row["status"],
        "environment": row["environment"],
    }


def insert_withdrawal(as_of, requested_paise, fee_paise, tax_paise, refund_paise, adjustment_paise, net_paise, status, environment, created_at=None):
    withdrawal_id = f"wd_{uuid.uuid4().hex[:12]}"
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO withdrawals
           (withdrawal_id, created_at, as_of, requested_paise, fee_paise, tax_paise,
            refund_paise, adjustment_paise, net_paise, status, environment)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            withdrawal_id, created_at, as_of, requested_paise, fee_paise, tax_paise,
            refund_paise, adjustment_paise, net_paise, status, environment,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM withdrawals WHERE withdrawal_id = ?", (withdrawal_id,)).fetchone()
    conn.close()
    return _public_withdrawal(dict(row))


def list_withdrawals(query: str = "", start=None, end=None, limit: int = 100):
    conn = get_db()
    clauses = ["1=1"]
    params: list = []
    if start:
        clauses.append("created_at >= ?")
        params.append(str(start))
    if end:
        clauses.append("created_at <= ?")
        params.append(str(end))
    if query:
        clauses.append("(withdrawal_id LIKE ? OR status LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like])
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM withdrawals WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [_public_withdrawal(dict(r)) for r in rows]


def sum_withdrawn_paise() -> int:
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(requested_paise), 0) AS total FROM withdrawals WHERE status = 'completed'"
    ).fetchone()
    conn.close()
    return int(row["total"] if row else 0)


def clear_withdrawals():
    conn = get_db()
    conn.execute("DELETE FROM withdrawals")
    conn.commit()
    conn.close()


def insert_store_order(payment_id, order_id, amount_paise, status, outcome, items_json, customer_name, customer_email, payment_method):
    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO store_orders
           (payment_id, order_id, created_at, amount_paise, refunded_paise, status, outcome,
            items_json, customer_name, customer_email, payment_method)
           VALUES (?,?,?,?,0,?,?,?,?,?,?)""",
        (
            payment_id, order_id, now_ist().isoformat(timespec="seconds"), int(amount_paise or 0),
            status, outcome, items_json, customer_name, customer_email, payment_method,
        ),
    )
    conn.commit()
    conn.close()


def get_store_order(payment_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM store_orders WHERE payment_id = ?", (payment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_store_orders(limit: int = 100):
    conn = get_db()
    rows = conn.execute("SELECT * FROM store_orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_store_order_refund(payment_id: str, refunded_paise: int, status: str):
    conn = get_db()
    conn.execute(
        "UPDATE store_orders SET refunded_paise = ?, status = ? WHERE payment_id = ?",
        (int(refunded_paise), status, payment_id),
    )
    conn.commit()
    conn.close()


def save_metric_snapshot(batch_id: str | None, payload: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO metric_snapshots (timestamp, batch_id, payload) VALUES (?,?,?)",
        (datetime.now(timezone.utc).isoformat(), batch_id, payload),
    )
    conn.commit()
    conn.close()


def list_metric_snapshots(limit: int = 20):
    conn = get_db()
    rows = conn.execute("SELECT * FROM metric_snapshots ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_resolution_memory(payment_id, mismatch_type, root_cause, resolution_category, payment_method, merchant_key, human_decision, evidence, amount_paise, actor):
    conn = get_db()
    conn.execute(
        """INSERT INTO resolution_memory
           (timestamp, payment_id, mismatch_type, root_cause, resolution_category, payment_method,
            merchant_key, human_decision, evidence, amount_paise, actor, enabled)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
        (
            datetime.now(timezone.utc).isoformat(), payment_id, mismatch_type, root_cause,
            resolution_category, payment_method, merchant_key, human_decision, evidence,
            amount_paise, actor,
        ),
    )
    conn.commit()
    conn.close()


def list_resolution_memory(mismatch_type: str | None = None, enabled_only: bool = True, limit: int = 200):
    conn = get_db()
    clauses = ["1=1"]
    params: list = []
    if mismatch_type:
        clauses.append("mismatch_type = ?")
        params.append(mismatch_type)
    if enabled_only:
        clauses.append("enabled = 1")
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM resolution_memory WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT ?",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_controller_rule(title, mismatch_type, payment_method, merchant_key, resolution_category, guidance, origin, actor):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO controller_rules
           (created_at, updated_at, title, mismatch_type, payment_method, merchant_key,
            resolution_category, guidance, enabled, origin, influence_count, actor)
           VALUES (?,?,?,?,?,?,?,?,1,?,0,?)""",
        (now, now, title, mismatch_type, payment_method, merchant_key, resolution_category, guidance, origin, actor),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM controller_rules WHERE id = ?", (cursor.lastrowid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_controller_rules():
    conn = get_db()
    rows = conn.execute("SELECT * FROM controller_rules ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_controller_rule(rule_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM controller_rules WHERE id = ?", (rule_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_controller_rule(rule_id: int, **fields):
    allowed = {
        "title", "mismatch_type", "payment_method", "merchant_key", "resolution_category",
        "guidance", "enabled", "origin",
    }
    updates = {key: value for key, value in fields.items() if key in allowed and value is not None}
    if not updates:
        return get_controller_rule(rule_id)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    assignments = ", ".join(f"{key} = ?" for key in updates)
    conn = get_db()
    conn.execute(
        f"UPDATE controller_rules SET {assignments} WHERE id = ?",
        [*updates.values(), rule_id],
    )
    conn.commit()
    conn.close()
    return get_controller_rule(rule_id)


def delete_controller_rule(rule_id: int) -> bool:
    conn = get_db()
    cursor = conn.execute("DELETE FROM controller_rules WHERE id = ?", (rule_id,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted == 1


def bump_rule_influence(rule_id: int):
    conn = get_db()
    conn.execute(
        "UPDATE controller_rules SET influence_count = influence_count + 1, updated_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), rule_id),
    )
    conn.commit()
    conn.close()
