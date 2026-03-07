#!/usr/bin/env python3
"""Run all invoices through the full ingestion + validation pipeline and print a summary."""

from dotenv import load_dotenv
load_dotenv()

from functools import partial
from pathlib import Path

import ingestion
import inventory_db
import validation
from llm_extract import LLMConfigurationError

INVOICE_DIR = Path(__file__).resolve().parent / "data" / "invoices"

def get_invoice_files(invoice_dir: Path) -> list[Path]:
    files = []
    for p in sorted(invoice_dir.iterdir()):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in (".json", ".csv", ".xml", ".txt", ".pdf"):
            continue
        files.append(p)
    return files


def run_all() -> None:
    # Fresh inventory DB for this run
    inventory_db.init_inventory_db()

    files = get_invoice_files(INVOICE_DIR)
    print(f"Processing {len(files)} invoice files\n")
    print("=" * 72)

    results = []

    for fp in files:
        print(f"\n[{fp.name}]")

        # --- Ingestion ---
        try:
            bundle = ingestion.ingest_invoice(fp)
        except FileNotFoundError as e:
            print(f"  INGEST ERROR: {e}")
            results.append((fp.name, "ingest_error", None))
            continue
        except ingestion.IngestionError as e:
            print(f"  INGEST ERROR: {e}")
            results.append((fp.name, "ingest_error", None))
            continue
        except LLMConfigurationError as e:
            print(f"  INGEST ERROR (LLM not configured): {e}")
            results.append((fp.name, "ingest_error", None))
            continue
        except Exception as e:
            print(f"  INGEST ERROR ({type(e).__name__}): {e}")
            results.append((fp.name, "ingest_error", None))
            continue

        inv = bundle.invoice
        print(f"  Invoice : {inv.invoice_number}")
        print(f"  Vendor  : {inv.vendor_name or '(empty)'}")
        print(f"  Total   : ${inv.total:,.2f}" if inv.total is not None else "  Total   : (none)")
        print(f"  Items   : {len(bundle.line_items)}")

        # --- Validation ---
        result = validation.validate_invoice(
            bundle,
            get_item=inventory_db.get_item,
            is_fraud_item=inventory_db.is_fraud_item,
        )

        status_label = "PASSED" if result.passed else "FAILED"
        print(f"  Validation: {status_label}")

        for flag in result.flags:
            symbol = "✗" if flag.severity.value == "HARD_FAIL" else "⚠"
            print(f"    {symbol} [{flag.severity.value}] {flag.category}: {flag.message}")

        if result.arithmetic_check and not result.arithmetic_check.matches:
            a = result.arithmetic_check
            print(f"    → Arithmetic discrepancy: ${a.discrepancy:,.2f}")

        results.append((fp.name, status_label, result))

    # --- Final summary table ---
    print("\n" + "=" * 72)
    print(f"{'FILE':<30} {'STATUS':<8}  FLAGS")
    print("-" * 72)
    for name, status, result in results:
        if result is None:
            print(f"  {name:<28} {'ERROR':<8}  —")
            continue
        hard = sum(1 for f in result.flags if f.severity.value == "HARD_FAIL")
        warn = sum(1 for f in result.flags if f.severity.value == "WARNING")
        flag_summary = f"{hard} HARD_FAIL, {warn} WARNING" if result.flags else "clean"
        marker = "✓" if result.passed else "✗"
        print(f"  {name:<28} {marker} {status:<6}  {flag_summary}")

    passed = sum(1 for _, s, _ in results if s == "PASSED")
    failed = sum(1 for _, s, _ in results if s == "FAILED")
    errors = sum(1 for _, s, _ in results if s == "ingest_error")
    print("-" * 72)
    print(f"  Total: {len(results)}  |  Passed: {passed}  |  Failed: {failed}  |  Errors: {errors}")


if __name__ == "__main__":
    run_all()
