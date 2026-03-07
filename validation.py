"""Validation module: check invoice against inventory and business rules.

Checks performed (in order):
  1. Empty vendor           → HARD_FAIL
  2. Negative quantity      → HARD_FAIL  (per line item; qty < 0)
  3. Fake / fraud item      → HARD_FAIL  (per line item; in FRAUD_ITEMS list)
  4. Aggregate quantities per normalized item name, then for each:
       - Unknown item       → HARD_FAIL  (not in inventory even after fuzzy match)
       - Zero stock         → WARNING    (item exists but stock == 0)
       - Stock exceeded     → HARD_FAIL  (agg_qty > stock > 0)
  5. Currency mismatch      → WARNING    (non-USD)
  6. Arithmetic mismatch    → WARNING    (computed total != claimed total)
  7. Duplicate invoice      → WARNING    (same invoice_number processed before)

passed = True only when there are zero HARD_FAIL flags.
Duplicate is recorded only when the invoice passes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Callable

import inventory_db
from arithmetic import verify_arithmetic
from models import (
    ArithmeticResult,
    Flag,
    InvoiceBundle,
    ItemMatch,
    MatchType,
    Severity,
    ValidationResult,
)
from normalizer import normalize_item_name

logger = logging.getLogger(__name__)


def validate_invoice(
    bundle: InvoiceBundle,
    get_item: Callable[[str], dict | None],
    is_fraud_item: Callable[[str], bool],
    db_path: Path | str | None = None,
) -> ValidationResult:
    """Validate an invoice bundle against inventory and business rules.

    Args:
        bundle:        Extracted and normalized invoice.
        get_item:      Callable for exact inventory lookup (from inventory_db).
        is_fraud_item: Callable to check fraud/blacklist (from inventory_db).
        db_path:       Path to inventory.db for fuzzy matching and duplicate
                       tracking. Defaults to project-root inventory.db.

    Returns:
        ValidationResult with passed flag, structured flags, item_matches,
        aggregate_quantities, and arithmetic_check.
    """
    inv = bundle.invoice
    flags: list[Flag] = []
    item_matches: list[ItemMatch] = []

    # ------------------------------------------------------------------
    # 1. Empty vendor
    # ------------------------------------------------------------------
    if not (inv.vendor_name or "").strip():
        flags.append(Flag(
            severity=Severity.HARD_FAIL,
            category="empty_vendor",
            message="Invoice vendor is empty or missing",
            field="vendor_name",
        ))

    # ------------------------------------------------------------------
    # 2. Negative quantity (per line item)
    # ------------------------------------------------------------------
    # Track which normalized item names already have a hard failure so we
    # skip them in the aggregate stock check (avoids confusing double-flagging).
    hard_failed_items: set[str] = set()

    for li in bundle.line_items:
        if li.quantity < 0:
            flags.append(Flag(
                severity=Severity.HARD_FAIL,
                category="negative_quantity",
                message=f"{li.item} has negative quantity: {li.quantity}",
                field="quantity",
                details=f"item={li.item}, qty={li.quantity}",
            ))
            hard_failed_items.add(normalize_item_name(li.item))

    # ------------------------------------------------------------------
    # 3. Fake / fraud item (per line item)
    # ------------------------------------------------------------------
    for li in bundle.line_items:
        norm = normalize_item_name(li.item)
        if is_fraud_item(norm) or is_fraud_item(li.item):
            flags.append(Flag(
                severity=Severity.HARD_FAIL,
                category="fake_item",
                message=f"{li.item} is a known fraudulent item",
                field="item",
                details=f"item={li.item}",
            ))
            hard_failed_items.add(norm)

    # ------------------------------------------------------------------
    # 4. Aggregate quantities per normalized item name, then stock check
    # ------------------------------------------------------------------
    agg_quantities: dict[str, float] = defaultdict(float)
    for li in bundle.line_items:
        norm = normalize_item_name(li.item)
        agg_quantities[norm] += li.quantity

    for norm_name, agg_qty in agg_quantities.items():
        # Skip items that already triggered a hard failure (negative qty, fraud).
        # Still record an ItemMatch so the result is complete.
        if norm_name in hard_failed_items:
            item_matches.append(ItemMatch(
                item_name=norm_name,
                matched_to=None,
                match_type=MatchType.unknown,
            ))
            continue

        # --- Exact inventory lookup ---
        record = get_item(norm_name)

        if record is not None:
            matched_to = record["item"]
            stock: int = record["stock"]
            match_type = MatchType.exact
            similarity = None
        else:
            # --- Fuzzy fallback ---
            fuzzy = inventory_db.fuzzy_match_item(norm_name, db_path=db_path)
            if fuzzy["found"]:
                matched_to = fuzzy["best_match"]
                similarity = fuzzy["similarity_score"]
                match_type = MatchType.fuzzy
                # Re-fetch stock for the fuzzy-matched item
                fuzzy_record = get_item(matched_to)
                stock = fuzzy_record["stock"] if fuzzy_record else 0
            else:
                # Unknown item — not in inventory at all
                item_matches.append(ItemMatch(
                    item_name=norm_name,
                    matched_to=None,
                    match_type=MatchType.unknown,
                ))
                if agg_qty > 0:
                    flags.append(Flag(
                        severity=Severity.HARD_FAIL,
                        category="unknown_item",
                        message=f"{norm_name} not found in inventory",
                        field="item",
                        details=f"item={norm_name}",
                    ))
                continue

        item_matches.append(ItemMatch(
            item_name=norm_name,
            matched_to=matched_to,
            match_type=match_type,
            similarity_score=similarity,
        ))

        # Stock check only matters when actually ordering (agg_qty > 0)
        if agg_qty > 0 and agg_qty > stock:
            if stock == 0:
                # Item exists in catalogue but has zero stock — WARNING so the
                # invoice can still reach human review rather than auto-rejecting.
                flags.append(Flag(
                    severity=Severity.WARNING,
                    category="zero_stock_item",
                    message=f"{matched_to} has zero stock (requested {agg_qty})",
                    field="quantity",
                    details=f"item={matched_to}, requested={agg_qty}, stock=0",
                ))
            else:
                flags.append(Flag(
                    severity=Severity.HARD_FAIL,
                    category="stock_exceeded",
                    message=f"{matched_to} requested {agg_qty}, only {stock} in stock",
                    field="quantity",
                    details=f"item={matched_to}, requested={agg_qty}, stock={stock}",
                ))

    # ------------------------------------------------------------------
    # 5. Currency mismatch
    # ------------------------------------------------------------------
    if inv.currency and inv.currency != "USD":
        flags.append(Flag(
            severity=Severity.WARNING,
            category="currency_mismatch",
            message=f"Invoice currency is {inv.currency}, expected USD",
            field="currency",
        ))

    # ------------------------------------------------------------------
    # 6. Arithmetic check
    # ------------------------------------------------------------------
    arith: ArithmeticResult = verify_arithmetic(
        line_items=bundle.line_items,
        claimed_subtotal=inv.subtotal,
        claimed_total=inv.total,
        tax_rate=inv.tax_rate,
        shipping=inv.shipping,
        tax_amount=inv.tax_amount,
    )
    if not arith.matches:
        flags.append(Flag(
            severity=Severity.WARNING,
            category="arithmetic_mismatch",
            message=(
                f"Math error: computed ${arith.computed_total:,.2f}, "
                f"claimed ${arith.claimed_total:,.2f}, "
                f"discrepancy ${arith.discrepancy:,.2f}"
            ),
            field="total",
            details=f"discrepancy={arith.discrepancy}",
        ))

    # ------------------------------------------------------------------
    # 7. Duplicate invoice detection
    # ------------------------------------------------------------------
    if inventory_db.is_duplicate(inv.invoice_number, db_path=db_path):
        flags.append(Flag(
            severity=Severity.WARNING,
            category="duplicate_invoice",
            message=f"Invoice {inv.invoice_number} has been processed before",
            field="invoice_number",
        ))

    # ------------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------------
    passed = not any(f.severity == Severity.HARD_FAIL for f in flags)

    # Record only passing invoices — failing ones can be corrected and resubmitted.
    if passed:
        inventory_db.mark_processed(inv.invoice_number, db_path=db_path)

    n_hard = sum(1 for f in flags if f.severity == Severity.HARD_FAIL)
    n_warn = sum(1 for f in flags if f.severity == Severity.WARNING)
    logger.info(
        "Validation %s — %d flag(s): %d HARD_FAIL, %d WARNING",
        "PASSED" if passed else "FAILED",
        len(flags),
        n_hard,
        n_warn,
    )

    return ValidationResult(
        passed=passed,
        flags=flags,
        item_matches=item_matches,
        aggregate_quantities=dict(agg_quantities),
        arithmetic_check=arith,
    )
