"""Arithmetic verification for invoice totals.

Computes expected total from line items and compares against the claimed total.
Tax rate (if present) must already be in decimal form (0.07, not 7).
"""

from __future__ import annotations

from typing import Optional

from src.core.models import ArithmeticResult, LineItem


def verify_arithmetic(
    line_items: list[LineItem],
    claimed_subtotal: Optional[float],
    claimed_total: Optional[float],
    tax_rate: Optional[float] = None,
    shipping: Optional[float] = None,
    tax_amount: Optional[float] = None,
) -> ArithmeticResult:
    """Compare the invoice's claimed total against what the line items compute to.

    Formula:
        computed_subtotal = sum(li.quantity * li.unit_price for li in line_items)
        computed_total    = computed_subtotal * (1 + tax_rate) + shipping
        discrepancy       = claimed_total - computed_total
        matches           = abs(discrepancy) < 0.01

    Args:
        line_items:       Line items from the invoice.
        claimed_subtotal: Subtotal as stated on the invoice (informational).
        claimed_total:    Total as stated on the invoice. If None, skip check (matches=True).
        tax_rate:         Decimal tax rate (e.g. 0.05 for 5%). None means no tax applied.
        shipping:         Shipping charge to add after tax. None means no shipping.

    Returns:
        ArithmeticResult with computed_total, claimed_total, matches, discrepancy.
    """
    computed_subtotal = round(
        sum(li.quantity * li.unit_price for li in line_items), 2
    )

    if tax_rate is not None and tax_rate != 0.0:
        computed_total = round(computed_subtotal * (1 + tax_rate), 2)
    elif tax_amount is not None and tax_amount != 0.0:
        computed_total = round(computed_subtotal + tax_amount, 2)
    else:
        computed_total = computed_subtotal

    if shipping is not None and shipping != 0.0:
        computed_total = round(computed_total + shipping, 2)

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
