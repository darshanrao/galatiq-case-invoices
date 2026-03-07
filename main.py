#!/usr/bin/env python3
"""CLI runner for the invoice processing pipeline."""

from dotenv import load_dotenv

load_dotenv()

import argparse
from functools import partial
from pathlib import Path

import ingestion
import inventory_db
import validation
from llm_extract import LLMConfigurationError


def main() -> None:
    parser = argparse.ArgumentParser(description="Process an invoice through ingestion and validation.")
    parser.add_argument(
        "--invoice_path",
        required=True,
        help="Path to the invoice file (TXT, JSON, or CSV)",
    )
    parser.add_argument(
        "--db_path",
        default=None,
        help="Path to inventory.db (default: project root)",
    )
    args = parser.parse_args()

    # Initialize inventory database
    inventory_db.init_inventory_db(args.db_path)

    # Ingest invoice
    print(f"Ingesting: {args.invoice_path}")
    try:
        bundle = ingestion.ingest_invoice(args.invoice_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return
    except ingestion.IngestionError as e:
        print(f"ERROR: Could not extract complete invoice: {e}")
        return
    except LLMConfigurationError as e:
        print(f"ERROR: {e}")
        return
    except Exception as e:
        print(f"ERROR during ingestion: {e}")
        raise

    inv = bundle.invoice
    print(f"\n--- Invoice: {inv.invoice_number} ---")
    print(f"Vendor: {inv.vendor_name}")
    if inv.total is not None:
        print(f"Total: ${inv.total:,.2f}")
    print(f"Line items: {len(bundle.line_items)}")

    # Validate
    get_item = partial(inventory_db.get_item, db_path=args.db_path) if args.db_path else inventory_db.get_item
    result = validation.validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
    )

    # Summary
    print(f"\n--- Validation Result ---")
    print(f"Overall status: {result.overall_status}")
    for r in result.line_item_results:
        symbol = "✓" if r.status == "valid" else "✗"
        print(f"  {symbol} {r.item} (qty {r.quantity}): {r.status} - {r.message}")
    if result.issues:
        print("\nIssues:")
        for issue in result.issues:
            print(f"  - {issue}")


if __name__ == "__main__":
    main()
