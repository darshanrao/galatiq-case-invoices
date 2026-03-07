"""SQLite inventory database and fraud-items list for invoice validation."""

import difflib
import sqlite3
from pathlib import Path

# Default DB path in project root
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "inventory.db"

# Items we know are fraudulent (fake); NOT in inventory
FRAUD_ITEMS: frozenset[str] = frozenset({"FakeItem"})

# Seed data for inventory: (item, stock) — schema unchanged
INVENTORY_SEED: list[tuple[str, int]] = [
    ("WidgetA", 15),
    ("WidgetB", 10),
    ("GadgetX", 5),
    ("GadgetZ", 0),  # Real item with zero stock for testing out_of_stock
]


def init_inventory_db(db_path: Path | str | None = None) -> None:
    """Create or reset the inventory database and seed it."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS inventory (item TEXT PRIMARY KEY, stock INTEGER)"
    )
    cursor.execute("DELETE FROM inventory")
    cursor.executemany("INSERT INTO inventory VALUES (?, ?)", INVENTORY_SEED)
    conn.commit()
    conn.close()


def get_item(item_name: str, db_path: Path | str | None = None) -> dict | None:
    """Look up an item in inventory by exact name. Returns None if not found."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT item, stock FROM inventory WHERE item = ?", (item_name,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return None
    return {"item": row["item"], "stock": row["stock"]}


def is_fraud_item(item_name: str) -> bool:
    """Check if an item is on the fraud/blacklist (known fake product)."""
    return item_name in FRAUD_ITEMS


# ---------------------------------------------------------------------------
# Fuzzy item matching
# ---------------------------------------------------------------------------


def _get_all_items(db_path: Path) -> list[str]:
    """Return all item names from inventory."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("SELECT item FROM inventory")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def fuzzy_match_item(
    item_name: str,
    db_path: Path | str | None = None,
    threshold: float = 0.9,
) -> dict:
    """Fuzzy match an item name against all inventory items.

    Two-step approach:
      1. Collapse internal spaces and try exact match — handles OCR artifacts
         like 'Widget A' resolving to 'WidgetA'.
      2. difflib fuzzy match on the original name at the given threshold.
         Default threshold 0.9 prevents false positives (e.g. 'WidgetC' → 'WidgetA'
         scores ~0.857 and is correctly rejected at 0.9).

    Returns:
        {"found": bool, "best_match": str|None, "similarity_score": float}
    """
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    all_items = _get_all_items(path)

    # Step 1: exact match after collapsing spaces
    normalized = item_name.replace(" ", "")
    if normalized in all_items:
        return {"found": True, "best_match": normalized, "similarity_score": 1.0}

    # Step 2: pure fuzzy match on original name
    matches = difflib.get_close_matches(item_name, all_items, n=1, cutoff=threshold)
    if matches:
        best = matches[0]
        score = difflib.SequenceMatcher(None, item_name, best).ratio()
        return {"found": True, "best_match": best, "similarity_score": round(score, 4)}

    return {"found": False, "best_match": None, "similarity_score": 0.0}


# ---------------------------------------------------------------------------
# Duplicate invoice tracking
# ---------------------------------------------------------------------------


def _ensure_processed_table(db_path: Path) -> None:
    """Create the processed_invoices table if it doesn't exist."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_invoices (
                invoice_number TEXT PRIMARY KEY,
                processed_at   TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def is_duplicate(invoice_number: str, db_path: Path | str | None = None) -> bool:
    """Return True if this invoice number has been processed before."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    _ensure_processed_table(path)
    conn = sqlite3.connect(str(path))
    try:
        cursor = conn.execute(
            "SELECT 1 FROM processed_invoices WHERE invoice_number = ?",
            (invoice_number,),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def mark_processed(invoice_number: str, db_path: Path | str | None = None) -> None:
    """Record this invoice number so future runs detect it as a duplicate."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    _ensure_processed_table(path)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            "INSERT OR IGNORE INTO processed_invoices "
            "(invoice_number, processed_at) VALUES (?, datetime('now'))",
            (invoice_number,),
        )
        conn.commit()
    finally:
        conn.close()
