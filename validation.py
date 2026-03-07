"""Validation module: check invoice line items against inventory and fraud list."""

from typing import Callable

from models import (
    InvoiceBundle,
    LineItem,
    LineItemValidationResult,
    ValidationResult,
)


def validate_invoice(
    bundle: InvoiceBundle,
    get_item: Callable[[str], dict | None],
    is_fraud_item: Callable[[str], bool],
) -> ValidationResult:
    """
    Validate an invoice against inventory and fraud list.

    Order of checks (mutually exclusive per line):
    1. invalid_quantity - quantity <= 0
    2. fake_item - item in fraud list (fraudulent)
    3. unknown_item - item not in inventory
    4. out_of_stock - item in inventory, stock == 0
    5. stock_mismatch - item in inventory, stock > 0, quantity > stock
    6. valid - otherwise
    """
    line_results: list[LineItemValidationResult] = []
    issues: list[str] = []

    for li in bundle.line_items:
        result = _validate_line_item(li, get_item, is_fraud_item)
        line_results.append(result)
        if result.status != "valid":
            issues.append(f"{li.item} (qty {li.quantity}): {result.message}")

    # Overall status
    bad_statuses = {"invalid_quantity", "fake_item", "unknown_item", "out_of_stock", "stock_mismatch"}
    has_bad = any(r.status in bad_statuses for r in line_results)
    overall_status = "invalid" if has_bad else "valid"

    return ValidationResult(
        invoice_number=bundle.invoice.invoice_number,
        overall_status=overall_status,
        line_item_results=line_results,
        issues=issues,
    )


def _validate_line_item(
    li: LineItem,
    get_item: Callable[[str], dict | None],
    is_fraud_item: Callable[[str], bool],
) -> LineItemValidationResult:
    """Validate a single line item. Checks are OR/mutually exclusive."""
    # 1. Data integrity: invalid quantity
    if li.quantity <= 0:
        return LineItemValidationResult(
            item=li.item,
            quantity=li.quantity,
            status="invalid_quantity",
            message="Quantity must be positive",
        )

    # 2. Fraud / fake item (in fraud list)
    if is_fraud_item(li.item):
        return LineItemValidationResult(
            item=li.item,
            quantity=li.quantity,
            status="fake_item",
            message="Item is on fraud list; fraudulent product",
        )

    # 3. Unknown item (not in inventory)
    record = get_item(li.item)
    if record is None:
        return LineItemValidationResult(
            item=li.item,
            quantity=li.quantity,
            status="unknown_item",
            message="Item not found in inventory",
        )

    stock = record["stock"]

    # 4. Out of stock (real item, stock == 0)
    if stock == 0:
        return LineItemValidationResult(
            item=li.item,
            quantity=li.quantity,
            status="out_of_stock",
            message="Item is out of stock (0 available)",
        )

    # 5. Stock mismatch (quantity exceeds available stock)
    if li.quantity > stock:
        return LineItemValidationResult(
            item=li.item,
            quantity=li.quantity,
            status="stock_mismatch",
            message=f"Quantity {li.quantity} exceeds available stock ({stock})",
        )

    # 6. Valid
    return LineItemValidationResult(
        item=li.item,
        quantity=li.quantity,
        status="valid",
        message="OK",
    )
