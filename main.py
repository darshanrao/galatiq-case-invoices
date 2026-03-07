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
        db_path=args.db_path,
    )

    # Summary
    print(f"\n--- Validation Result ---")
    print(f"Overall: {'PASSED' if result.passed else 'FAILED'}")

    if result.flags:
        print("\nFlags:")
        for flag in result.flags:
            symbol = "✗" if flag.severity.value == "HARD_FAIL" else "⚠"
            print(f"  {symbol} [{flag.severity.value}] {flag.category}: {flag.message}")

    if result.item_matches:
        print("\nItem matches:")
        for m in result.item_matches:
            if m.matched_to:
                tag = f"→ {m.matched_to} ({m.match_type.value})"
                if m.similarity_score and m.similarity_score < 1.0:
                    tag += f" score={m.similarity_score}"
            else:
                tag = "NOT FOUND"
            print(f"  {m.item_name}: {tag}")

    if result.arithmetic_check:
        a = result.arithmetic_check
        arith_status = "OK" if a.matches else f"DISCREPANCY ${a.discrepancy:,.2f}"
        print(f"\nArithmetic: computed=${a.computed_total:,.2f}  claimed=${a.claimed_total:,.2f}  {arith_status}")


if __name__ == "__main__":
    main()
