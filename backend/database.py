"""
Database setup for Razor-AI. A single SQLite file holds two tables:
- transactions: the loaded synthetic batch
- reconciled: the same records after reconciliation.py has processed them
- audit_trail: a log of every match, exception, explanation, and chat query

SQLite is deliberately chosen over a bigger database for this prototype --
it's a single file, needs no separate server process, and is more than
sufficient for a demo-scale batch. Swapping to Postgres later (for a real
production deployment) would only require changing this file, since nothing
else in the codebase talks to the database directly.
"""

import sqlite3
from datetime import datetime, timezone

DB_PATH = "razorai.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name, not just index
    return conn


def init_db():
    """Creates the audit_trail table if it doesn't already exist. Safe to call on every startup."""
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
    conn.commit()
    conn.close()


def log_audit(action_type: str, record_ids, details: str, source: str):
    """
    source should be 'rule_engine' or 'gemini_api' -- this distinction is
    what lets the frontend show which actions involved AI and which didn't.
    """
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_trail (timestamp, action_type, record_ids, details, source) VALUES (?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), action_type, str(record_ids), details, source),
    )
    conn.commit()
    conn.close()


def get_audit_trail(limit: int = 100):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM audit_trail ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reset_db():
    """
    Drops and recreates the audit_trail table, and clears transactions/
    reconciled if they exist. Used by the /demo/reset endpoint so one
    judge's clicking around doesn't leave stale state for the next person
    to see.
    """
    conn = get_db()
    conn.execute("DROP TABLE IF EXISTS audit_trail")
    conn.execute("DROP TABLE IF EXISTS transactions")
    conn.execute("DROP TABLE IF EXISTS reconciled")
    conn.commit()
    conn.close()
    init_db()
