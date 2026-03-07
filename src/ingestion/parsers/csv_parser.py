"""CSV invoice parser."""

import csv
from io import StringIO

from src.core.models import Invoice, InvoiceBundle, LineItem
from src.ingestion.normalizer import normalize_date, normalize_invoice_number, normalize_item_name

from .utils import _parse_currency, _parse_int


def parse_csv(content: str) -> InvoiceBundle:
    """Parse CSV invoice. Supports both row-per-line and key-value formats."""
    rows = list(csv.reader(StringIO(content)))

    if not rows:
        return InvoiceBundle(invoice=Invoice(invoice_number="", vendor_name=""))

    # Detect format: key-value (field,value) vs row-per-line (headers with Item, Qty, etc.)
    first_row = [c.strip().lower() for c in rows[0]]
    if "field" in first_row and "value" in first_row:
        return _ingest_csv_keyvalue(rows)
    return _ingest_csv_row_per_line(rows)


def _ingest_csv_keyvalue(rows: list[list[str]]) -> InvoiceBundle:
    """Parse key-value CSV (e.g. invoice_1006)."""
    kv: dict[str, str] = {}
    line_items: list[LineItem] = []
    current_item: dict[str, str] = {}

    for row in rows[1:]:
        if len(row) < 2:
            continue
        field_name = row[0].strip().lower()
        value = row[1].strip()

        if field_name == "item":
            if current_item and current_item.get("item"):
                qty = _parse_int(current_item.get("quantity")) or 0
                up = _parse_currency(current_item.get("unit_price")) or 0.0
                line_items.append(
                    LineItem(
                        item=normalize_item_name(current_item["item"]),
                        quantity=qty,
                        unit_price=up,
                        line_total=qty * up if qty and up else None,
                    )
                )
            current_item = {"item": value}
        elif field_name == "quantity":
            current_item["quantity"] = value
        elif field_name == "unit_price":
            current_item["unit_price"] = value
        else:
            kv[field_name] = value

    if current_item and current_item.get("item"):
        qty = _parse_int(current_item.get("quantity")) or 0
        up = _parse_currency(current_item.get("unit_price")) or 0.0
        line_items.append(
            LineItem(
                item=normalize_item_name(current_item["item"]),
                quantity=qty,
                unit_price=up,
                line_total=qty * up if qty and up else None,
            )
        )

    inv = Invoice(
        invoice_number=normalize_invoice_number(kv.get("invoice_number", "")),
        vendor_name=kv.get("vendor", ""),
        invoice_date=normalize_date(kv.get("date")) if kv.get("date") else None,
        due_date=normalize_date(kv.get("due_date")) if kv.get("due_date") else None,
        payment_terms=kv.get("payment_terms"),
        subtotal=_parse_currency(kv.get("subtotal")),
        tax_amount=_parse_currency(kv.get("tax")),
        total=_parse_currency(kv.get("total")),
    )
    return InvoiceBundle(invoice=inv, line_items=line_items)


def _ingest_csv_row_per_line(rows: list[list[str]]) -> InvoiceBundle:
    """Parse row-per-line CSV (e.g. invoice_1007)."""
    headers = [c.strip().lower() for c in rows[0]]
    col_idx = {h: i for i, h in enumerate(headers)}

    inv_number = ""
    vendor_name = ""
    inv_date = ""
    due_date = ""
    line_items: list[LineItem] = []

    for row in rows[1:]:
        # Row with invoice header
        if len(row) > col_idx.get("invoice_number", -1) and row[col_idx.get("invoice_number", 0)]:
            inv_number = row[col_idx.get("invoice_number", 0)]
        if len(row) > col_idx.get("vendor", -1) and row[col_idx.get("vendor", 0)]:
            vendor_name = row[col_idx.get("vendor", 0)]
        if len(row) > col_idx.get("date", -1) and row[col_idx.get("date", 0)]:
            inv_date = row[col_idx.get("date", 0)]
        if len(row) > col_idx.get("due date", -1) and row[col_idx.get("due date", 0)]:
            due_date = row[col_idx.get("due date", 0)]

        # Line item row (has item and qty)
        item_col = col_idx.get("item", -1)
        qty_col = col_idx.get("qty", col_idx.get("quantity", -1))
        if item_col >= 0 and qty_col >= 0 and len(row) > max(item_col, qty_col):
            item_val = row[item_col].strip()
            if item_val and not item_val.lower().startswith("subtotal") and not item_val.lower().startswith("tax") and not item_val.lower().startswith("total"):
                qty = _parse_int(row[qty_col]) or 0
                up_col = col_idx.get("unit price", col_idx.get("unit_price", -1))
                up = _parse_currency(row[up_col]) if up_col >= 0 and len(row) > up_col else 0.0
                lt_col = col_idx.get("line total", -1)
                lt = _parse_currency(row[lt_col]) if lt_col >= 0 and len(row) > lt_col else None
                if lt is None:
                    lt = qty * up if qty and up else None
                line_items.append(LineItem(item=normalize_item_name(item_val), quantity=qty, unit_price=up, line_total=lt))

    inv = Invoice(
        invoice_number=normalize_invoice_number(inv_number) if inv_number else "",
        vendor_name=vendor_name or "",
        invoice_date=normalize_date(inv_date) if inv_date else None,
        due_date=normalize_date(due_date) if due_date else None,
        payment_terms=None,
        subtotal=None,
        tax_amount=None,
        total=None,
    )
    return InvoiceBundle(invoice=inv, line_items=line_items)
