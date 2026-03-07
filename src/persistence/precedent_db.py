"""
Precedent database for the approval self-correction feedback loop.

Stores approval decisions keyed by flag pattern so the system can auto-decide
on recurring flag combinations without re-running the full LLM reflection loop.

Table schema:
    approval_history(
        flag_pattern  TEXT PRIMARY KEY,
        decision      TEXT,
        reasoning     TEXT,
        count         INTEGER,
        source        TEXT,
        processed_at  TEXT
    )

flag_pattern = "|".join(sorted({f.category for f in flags if f.severity == WARNING}))
Examples: "arithmetic_mismatch|duplicate_invoice", "currency_mismatch", "" (clean)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "precedent.db"


def _get_db_path(db_path=None) -> Path:
    return Path(db_path) if db_path else DEFAULT_DB_PATH


def _connect(db_path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_precedent_db(db_path=None) -> None:
    """Create the approval_history table if it doesn't exist."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approval_history (
                flag_pattern  TEXT PRIMARY KEY,
                decision      TEXT NOT NULL,
                reasoning     TEXT NOT NULL,
                count         INTEGER NOT NULL DEFAULT 1,
                source        TEXT NOT NULL DEFAULT 'llm',
                processed_at  TEXT NOT NULL
            )
        """)
        conn.commit()


def get_precedent(flag_pattern: str, db_path=None) -> dict | None:
    """Return the stored precedent for a flag pattern, or None if unseen.

    Returns a dict with keys: decision, reasoning, count, source.
    """
    init_precedent_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT decision, reasoning, count, source FROM approval_history WHERE flag_pattern = ?",
            (flag_pattern,),
        ).fetchone()
    if row is None:
        return None
    return {
        "decision": row["decision"],
        "reasoning": row["reasoning"],
        "count": row["count"],
        "source": row["source"],
    }


def store_decision(
    flag_pattern: str,
    decision: str,
    reasoning: str,
    source: str = "llm",
    db_path=None,
) -> None:
    """Upsert an approval decision for a flag pattern.

    - Same pattern + same decision → increment count.
    - Same pattern + different decision → reset count=1 (preference shifted).
    - New pattern → insert with count=1.
    """
    init_precedent_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT decision, count FROM approval_history WHERE flag_pattern = ?",
            (flag_pattern,),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO approval_history (flag_pattern, decision, reasoning, count, source, processed_at)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (flag_pattern, decision, reasoning, source, now),
            )
        elif existing["decision"] == decision:
            conn.execute(
                """
                UPDATE approval_history
                SET count = count + 1, reasoning = ?, source = ?, processed_at = ?
                WHERE flag_pattern = ?
                """,
                (reasoning, source, now, flag_pattern),
            )
        else:
            # Decision changed — reset counter, update reasoning and source.
            conn.execute(
                """
                UPDATE approval_history
                SET decision = ?, reasoning = ?, count = 1, source = ?, processed_at = ?
                WHERE flag_pattern = ?
                """,
                (decision, reasoning, source, now, flag_pattern),
            )
        conn.commit()


def record_human_override(
    flag_pattern: str,
    decision: str,
    reasoning: str,
    db_path=None,
) -> None:
    """Store a human override decision, immediately authoritative (count=3, source='human').

    Can be called externally to teach the system a business rule without waiting
    for the 3-consistent-decision threshold.
    """
    init_precedent_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO approval_history (flag_pattern, decision, reasoning, count, source, processed_at)
            VALUES (?, ?, ?, 3, 'human', ?)
            ON CONFLICT(flag_pattern) DO UPDATE SET
                decision = excluded.decision,
                reasoning = excluded.reasoning,
                count = 3,
                source = 'human',
                processed_at = excluded.processed_at
            """,
            (flag_pattern, decision, reasoning, now),
        )
        conn.commit()
