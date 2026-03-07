"""Arithmetic verification for invoice totals.

Computes expected total from line items and compares against the claimed total.
Tax rate (if present) must already be in decimal form (0.07, not 7).
"""

from __future__ import annotations

from typing import Optional

from models import ArithmeticResult, LineItem


def verify_arithmetic(
    line_items: list[LineItem],
    claimed_subtotal: Optional[float],
    claimed_total: Optional[float],
    tax_rate: Optional[float] = None,
) -> ArithmeticResult:
    """Compare the invoice's claimed total against what the line items compute to.

    Formula:
        computed_subtotal = sum(li.quantity * li.unit_price for li in line_items)
        computed_total    = computed_subtotal * (1 + tax_rate)  [if tax_rate given]
                          = computed_subtotal                    [otherwise]
        discrepancy       = claimed_total - computed_total
        matches           = abs(discrepancy) < 0.01

    Args:
        line_items:       Line items from the invoice.
        claimed_subtotal: Subtotal as stated on the invoice (informational, unused in
                          the match decision but validated implicitly via total).
        claimed_total:    Total as stated on the invoice. If None, skip check (matches=True).
        tax_rate:         Decimal tax rate (e.g. 0.07 for 7%). None means no tax applied.

    Returns:
        ArithmeticResult with computed_total, claimed_total, matches, discrepancy.
    """
    computed_subtotal = round(
        sum(li.quantity * li.unit_price for li in line_items), 2
    )

    if tax_rate is not None and tax_rate != 0.0:
        computed_total = round(computed_subtotal * (1 + tax_rate), 2)
    else:
        computed_total = computed_subtotal

    # Nothing to verify if the invoice didn't state a total
    if claimed_total is None:
        return ArithmeticResult(
            computed_total=computed_total,
            claimed_total=computed_total,
            matches=True,
            discrepancy=0.0,
        )

    claimed = round(claimed_total, 2)
    discrepancy = round(claimed - computed_total, 2)
    matches = abs(discrepancy) < 0.01

    return ArithmeticResult(
        computed_total=computed_total,
        claimed_total=claimed,
        matches=matches,
        discrepancy=discrepancy,
    )
