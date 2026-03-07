#!/usr/bin/env python3
"""Run all invoices through the full pipeline and print a summary."""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from pathlib import Path

from src.pipeline.runner import run

INVOICE_DIR = Path(__file__).resolve().parent.parent / "data" / "invoices"


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


def _final_status_label(state) -> str:
    """Map pipeline state to a short display label."""
    pr = state.get("payment_result")
    if pr is None:
        return "ERROR"
    if pr.status == "paid":
        return "PAID"
    stage = pr.rejection_stage or "unknown"
    return f"REJECTED({stage})"


def run_all() -> None:
    files = get_invoice_files(INVOICE_DIR)
    print(f"Processing {len(files)} invoice files\n")
    print("=" * 80)

    rows = []

    for fp in files:
        print(f"\n[{fp.name}]")
        try:
            state = run(str(fp))
        except Exception as exc:
            print(f"  PIPELINE ERROR: {exc}")
            rows.append((fp.name, "ERROR", str(exc)))
            continue

        bundle = state.get("invoice")
        if bundle:
            inv = bundle.invoice
            print(f"  Invoice : {inv.invoice_number}")
            print(f"  Vendor  : {inv.vendor_name or '(empty)'}")
            print(f"  Total   : ${inv.total:,.2f}" if inv.total is not None else "  Total   : (none)")
            print(f"  Items   : {len(bundle.line_items)}")

        vr = state.get("validation_result")
        if vr:
            print(f"  Validation: {'PASSED' if vr.passed else 'FAILED'}")
            for flag in vr.flags:
                symbol = "✗" if flag.severity.value == "HARD_FAIL" else "⚠"
                print(f"    {symbol} [{flag.severity.value}] {flag.category}: {flag.message}")

        ar = state.get("approval_result")
        if ar:
            print(f"  Approval: {ar.decision} [{ar.decision_source}] risk={ar.risk_score:.2f}")

        pr = state.get("payment_result")
        if pr:
            if pr.status == "paid":
                print(f"  Payment: PAID ${pr.amount:,.2f} to {pr.vendor}")
            else:
                print(f"  Payment: REJECTED at {pr.rejection_stage} — {pr.rejection_reason}")

        label = _final_status_label(state)
        rows.append((fp.name, label, ""))

    # --- Summary table ---
    print("\n" + "=" * 80)
    print(f"{'FILE':<32} {'STATUS'}")
    print("-" * 80)

    paid = rejected_validation = rejected_approval = errors = 0
    for name, label, _ in rows:
        print(f"  {name:<30} {label}")
        if label == "PAID":
            paid += 1
        elif "REJECTED(validation)" in label:
            rejected_validation += 1
        elif "REJECTED(approval)" in label:
            rejected_approval += 1
        elif label.startswith("REJECTED"):
            rejected_approval += 1  # ingestion / unknown
        else:
            errors += 1

    print("-" * 80)
    print(
        f"  Total: {len(rows)}  |  PAID: {paid}  |  "
        f"REJECTED(validation): {rejected_validation}  |  "
        f"REJECTED(approval): {rejected_approval}  |  ERRORS: {errors}"
    )


if __name__ == "__main__":
    run_all()
