"""
Invoice store backed by SQLite — single source of truth for all processed invoices.

Schema mirrors the pipeline stages so the dashboard can show real-time progress.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "invoice_store.db"


def _get_db_path(db_path=None) -> Path:
    return Path(db_path) if db_path else DEFAULT_DB_PATH


def _connect(db_path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_invoice_store(db_path=None) -> None:
    """Create the invoices table if it doesn't exist."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id                TEXT PRIMARY KEY,
                file_path         TEXT,
                original_filename TEXT,
                vendor            TEXT,
                amount            REAL,
                due_date          TEXT,
                status            TEXT NOT NULL DEFAULT 'processing',
                uploaded_at       TEXT NOT NULL,
                completed_at      TEXT,
                ingestion_data    TEXT,
                validation_data   TEXT,
                approval_data     TEXT,
                payment_data      TEXT,
                review_id         TEXT
            )
        """)
        conn.commit()


def create_invoice(id: str, filename: str, file_path: str, db_path=None) -> dict:
    """Insert a new invoice row with status=processing. Returns the new row as dict."""
    init_invoice_store(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO invoices (id, file_path, original_filename, status, uploaded_at)
            VALUES (?, ?, ?, 'processing', ?)
            """,
            (id, file_path, filename, now),
        )
        conn.commit()
    return get_invoice(id, db_path)


def update_stage(id: str, stage: str, data: dict[str, Any], db_path=None) -> None:
    """Update one stage JSON column and status for an invoice."""
    init_invoice_store(db_path)

    column_map = {
        "ingestion": "ingestion_data",
        "validation": "validation_data",
        "approval": "approval_data",
        "payment": "payment_data",
    }
    col = column_map.get(stage)

    now = datetime.now(timezone.utc).isoformat()
    status = data.get("status")

    # Extract top-level fields that belong in the main columns
    vendor = data.get("vendor")
    amount = data.get("amount")
    due_date = data.get("due_date")
    review_id = data.get("review_id")

    with _connect(db_path) as conn:
        if col:
            conn.execute(
                f"UPDATE invoices SET {col} = ? WHERE id = ?",
                (json.dumps(data), id),
            )

        if status:
            completed_at = now if status in ("paid", "rejected", "error") else None
            if status in ("paid", "rejected", "error", "pending_review", "approved"):
                conn.execute(
                    "UPDATE invoices SET status = ?, completed_at = ? WHERE id = ?",
                    (status, completed_at, id),
                )
            else:
                conn.execute(
                    "UPDATE invoices SET status = ? WHERE id = ?",
                    (status, id),
                )

        if vendor:
            conn.execute("UPDATE invoices SET vendor = ? WHERE id = ?", (vendor, id))
        if amount is not None:
            conn.execute("UPDATE invoices SET amount = ? WHERE id = ?", (amount, id))
        if due_date:
            conn.execute("UPDATE invoices SET due_date = ? WHERE id = ?", (due_date, id))
        if review_id:
            conn.execute("UPDATE invoices SET review_id = ? WHERE id = ?", (review_id, id))

        conn.commit()


def get_invoice(id: str, db_path=None) -> dict | None:
    """Fetch a single invoice by ID. Returns None if not found."""
    init_invoice_store(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    # Parse JSON columns
    for col in ("ingestion_data", "validation_data", "approval_data", "payment_data"):
        if result.get(col):
            try:
                result[col] = json.loads(result[col])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


def list_invoices(status: Optional[str] = None, vendor: Optional[str] = None, db_path=None) -> list[dict]:
    """List all invoices, optionally filtered by status and/or vendor."""
    init_invoice_store(db_path)
    with _connect(db_path) as conn:
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if vendor:
            conditions.append("vendor LIKE ?")
            params.append(f"%{vendor}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM invoices {where} ORDER BY uploaded_at DESC",
            params,
        ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        for col in ("ingestion_data", "validation_data", "approval_data", "payment_data"):
            if d.get(col):
                try:
                    d[col] = json.loads(d[col])
                except (json.JSONDecodeError, TypeError):
                    pass
        result.append(d)
    return result


def get_stats(db_path=None) -> dict:
    """Return counts by status."""
    init_invoice_store(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM invoices GROUP BY status"
        ).fetchall()
    counts = {row["status"]: row["count"] for row in rows}
    return {
        "total": sum(counts.values()),
        "processing": counts.get("processing", 0),
        "approved": counts.get("approved", 0),
        "paid": counts.get("paid", 0),
        "rejected": counts.get("rejected", 0),
        "pending_review": counts.get("pending_review", 0),
        "error": counts.get("error", 0),
    }


def generate_invoice_id() -> str:
    """Generate a unique invoice ID."""
    return f"INV-{uuid.uuid4().hex[:8].upper()}"
