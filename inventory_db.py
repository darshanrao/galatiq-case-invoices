"""SQLite inventory database and fraud-items list for invoice validation."""

import sqlite3
from pathlib import Path

# Default DB path in project root
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "inventory.db"

# Items we know are fraudulent (fake); NOT in inventory
FRAUD_ITEMS: frozenset[str] = frozenset({"FakeItem"})

# Seed data for inventory: (item, stock)
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
    """Look up an item in inventory. Returns None if not found."""
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
