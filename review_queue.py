"""
Human review queue backed by SQLite.

Stores invoices that couldn't be decided automatically (novel flag patterns)
so a human reviewer can approve or reject them via the dashboard.

On human decision:
    - record_human_override() is called → immediately authoritative in Tier 2.5
    - review row is updated with decision + decided_at
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import precedent_db

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "review_queue.db"


def _get_db_path(db_path=None) -> Path:
    return Path(db_path) if db_path else DEFAULT_DB_PATH


def _connect(db_path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_review_queue(db_path=None) -> None:
    """Create the review_queue table if it doesn't exist."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_queue (
                id                TEXT PRIMARY KEY,
                file_path         TEXT NOT NULL,
                invoice_number    TEXT NOT NULL,
                vendor            TEXT NOT NULL,
                amount            REAL NOT NULL,
                flag_pattern      TEXT NOT NULL,
                risk_score        REAL NOT NULL,
                recommendation    TEXT NOT NULL,
                flag_explanation  TEXT NOT NULL,
                status            TEXT NOT NULL DEFAULT 'pending',
                created_at        TEXT NOT NULL,
                decided_at        TEXT,
                decision_reasoning TEXT
            )
        """)
        conn.commit()


def enqueue(
    file_path: str,
    invoice_number: str,
    vendor: str,
    amount: float,
    flag_pattern: str,
    risk_score: float,
    recommendation: str,
    flag_explanation: str,
    db_path=None,
) -> str:
    """Add an invoice to the human review queue. Returns the new review ID."""
    init_review_queue(db_path)
    review_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO review_queue
              (id, file_path, invoice_number, vendor, amount, flag_pattern,
               risk_score, recommendation, flag_explanation, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (review_id, file_path, invoice_number, vendor, amount,
             flag_pattern, risk_score, recommendation, flag_explanation, now),
        )
        conn.commit()
    return review_id


def get_review(review_id: str, db_path=None) -> dict | None:
    """Fetch a single review by ID. Returns None if not found."""
    init_review_queue(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM review_queue WHERE id = ?", (review_id,)
        ).fetchone()
    return dict(row) if row else None


def list_reviews(status: Optional[str] = None, db_path=None) -> list[dict]:
    """List all reviews, optionally filtered by status ('pending'|'approved'|'rejected')."""
    init_review_queue(db_path)
    with _connect(db_path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM review_queue WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM review_queue ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def decide(
    review_id: str,
    decision: str,
    reasoning: str,
    db_path=None,
    precedent_db_path=None,
) -> dict:
    """Record a human decision on a pending review.

    - Updates the review row with decision + decided_at.
    - Calls record_human_override() so Tier 2.5 immediately learns this rule.

    Args:
        review_id:        UUID of the review to decide.
        decision:         "APPROVED" or "REJECTED".
        reasoning:        Human-provided explanation (stored as precedent reasoning).
        db_path:          Path to review_queue.db.
        precedent_db_path: Path to precedent.db (defaults to project root).

    Returns:
        Updated review dict.

    Raises:
        ValueError: if review not found or already decided.
    """
    init_review_queue(db_path)
    review = get_review(review_id, db_path)
    if review is None:
        raise ValueError(f"Review {review_id} not found")
    if review["status"] != "pending":
        raise ValueError(f"Review {review_id} is already {review['status']}")

    decision = decision.upper()
    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError(f"Decision must be APPROVED or REJECTED, got: {decision}")

    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE review_queue
            SET status = ?, decided_at = ?, decision_reasoning = ?
            WHERE id = ?
            """,
            (decision.lower(), now, reasoning, review_id),
        )
        conn.commit()

    # Teach Tier 2.5 immediately (count=3 → authoritative for future runs)
    precedent_db.record_human_override(
        flag_pattern=review["flag_pattern"],
        decision=decision,
        reasoning=reasoning,
        db_path=precedent_db_path,
    )

    return get_review(review_id, db_path)
