#!/usr/bin/env python3
"""CLI runner for the invoice processing pipeline."""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import argparse

from src.pipeline.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Process an invoice through the full pipeline.")
    parser.add_argument(
        "--invoice_path",
        required=True,
        help="Path to the invoice file (TXT, JSON, CSV, XML, PDF)",
    )
    parser.add_argument(
        "--db_path",
        default=None,
        help="Path to inventory.db (default: project root)",
    )
    args = parser.parse_args()

    print(f"Processing: {args.invoice_path}")
    state = run(args.invoice_path, db_path=args.db_path)

    # --- Invoice details ---
    bundle = state.get("invoice")
    if bundle:
        inv = bundle.invoice
        print(f"\n--- Invoice: {inv.invoice_number} ---")
        print(f"Vendor : {inv.vendor_name}")
        if inv.total is not None:
            print(f"Total  : ${inv.total:,.2f}")
        print(f"Items  : {len(bundle.line_items)}")

    # --- Validation ---
    vr = state.get("validation_result")
    if vr:
        print(f"\n--- Validation: {'PASSED' if vr.passed else 'FAILED'} ---")
        for flag in vr.flags:
            symbol = "✗" if flag.severity.value == "HARD_FAIL" else "⚠"
            print(f"  {symbol} [{flag.severity.value}] {flag.category}: {flag.message}")
        if vr.arithmetic_check:
            a = vr.arithmetic_check
            arith_status = "OK" if a.matches else f"DISCREPANCY ${a.discrepancy:,.2f}"
            print(f"  Arithmetic: computed=${a.computed_total:,.2f}  claimed=${a.claimed_total:,.2f}  {arith_status}")

    # --- Approval ---
    ar = state.get("approval_result")
    if ar:
        print(f"\n--- Approval: {ar.decision} ---")
        print(f"  Source     : {ar.decision_source}")
        print(f"  Risk score : {ar.risk_score:.2f}")
        print(f"  Reasoning  : {ar.final_reasoning}")
        if ar.decision_source not in ("deterministic", "auto_reject", "learned_precedent"):
            print(f"  Prosecution: {ar.prosecution_argument}")
            print(f"  Defense    : {ar.defense_argument}")

    # --- Payment ---
    pr = state.get("payment_result")
    if pr:
        print(f"\n--- Payment: {pr.status.upper()} ---")
        if pr.status == "paid":
            print(f"  Paid ${pr.amount:,.2f} to {pr.vendor}")
        else:
            print(f"  Stage   : {pr.rejection_stage}")
            print(f"  Reason  : {pr.rejection_reason}")

    # --- Final status ---
    print(f"\nFinal status: {state.get('status', 'unknown').upper()}")


if __name__ == "__main__":
    main()
