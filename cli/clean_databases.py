#!/usr/bin/env python3
"""Clean all application databases except inventory.db.

Clears data from:
  - invoice_store.db (invoices)
  - review_queue.db (review_queue)
  - precedent.db (approval_history)

Does NOT modify inventory.db.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

pathlib_path = Path(__file__).parent.parent
sys.path.insert(0, str(pathlib_path))

from dotenv import load_dotenv

load_dotenv()

from src.core.logging_config import configure_logging

configure_logging()

# DB paths (match persistence module defaults)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASES_TO_CLEAN = [
    (PROJECT_ROOT / "invoice_store.db", ["invoices"]),
    (PROJECT_ROOT / "review_queue.db", ["review_queue"]),
    (PROJECT_ROOT / "precedent.db", ["approval_history"]),
]
# inventory.db is explicitly excluded


def clean_database(db_path: Path, tables: list[str], dry_run: bool = False) -> tuple[int, bool]:
    """Delete all rows from the given tables. Returns (total_rows_deleted, success)."""
    if not db_path.exists():
        return 0, True  # Nothing to clean

    total_deleted = 0
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            if count > 0:
                if not dry_run:
                    cursor.execute(f"DELETE FROM {table}")
                total_deleted += count
        if not dry_run:
            conn.commit()
        conn.close()
        return total_deleted, True
    except sqlite3.Error as e:
        print(f"  Error: {e}", file=sys.stderr)
        return total_deleted, False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean all application databases except inventory.db."
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without making changes",
    )
    args = parser.parse_args()

    # Collect DBs that exist and have data
    to_clean: list[tuple[Path, list[str], int]] = []
    for db_path, tables in DATABASES_TO_CLEAN:
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                total = 0
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    total += cursor.fetchone()[0]
                conn.close()
                if total > 0:
                    to_clean.append((db_path, tables, total))
            except sqlite3.Error:
                to_clean.append((db_path, tables, -1))  # -1 = unknown

    if not to_clean:
        print("No data to clean. All databases are empty or do not exist.")
        return

    print("Databases to clean (inventory.db will NOT be modified):")
    for db_path, tables, count in to_clean:
        count_str = f"{count} row(s)" if count >= 0 else "?"
        print(f"  {db_path.name}: {tables} ({count_str})")

    if args.dry_run:
        print("\n[--dry-run] No changes made.")
        return

    if not args.yes:
        reply = input("\nProceed? [y/N]: ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted.")
            return

    print()
    for db_path, tables, _ in to_clean:
        deleted, ok = clean_database(db_path, tables, dry_run=False)
        status = f"cleaned {deleted} row(s)" if ok else "FAILED"
        print(f"  {db_path.name}: {status}")

    print("Done.")


if __name__ == "__main__":
    main()
