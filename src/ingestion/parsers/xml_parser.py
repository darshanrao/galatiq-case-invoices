"""XML invoice parser."""

import xml.etree.ElementTree as ET

from src.core.models import Invoice, InvoiceBundle, LineItem
from src.ingestion.normalizer import normalize_date, normalize_invoice_number, normalize_item_name

from .utils import _parse_currency, _parse_int


def parse_xml(content: str) -> InvoiceBundle:
    """Parse XML invoice. Handles structure with header, line_items, totals."""
    root = ET.fromstring(content)

    def get_text(parent: ET.Element, tag: str) -> str | None:
        el = parent.find(tag)
        return el.text.strip() if el is not None and el.text else None

    header = root.find("header") or root
    inv_num = get_text(header, "invoice_number") or ""
    vendor = get_text(header, "vendor") or ""
    date_str = get_text(header, "date")
    due_str = get_text(header, "due_date")
    currency = get_text(header, "currency") or "USD"
    payment_terms = get_text(root, "payment_terms")

    line_items: list[LineItem] = []
    items_el = root.find("line_items")
    if items_el is not None:
        for item_el in items_el.findall("item"):
            item_name = normalize_item_name(get_text(item_el, "name") or "")
            qty = _parse_int(get_text(item_el, "quantity")) or 0
            up = _parse_currency(get_text(item_el, "unit_price")) or 0.0
            lt = _parse_currency(get_text(item_el, "amount") or get_text(item_el, "line_total"))
            if lt is None:
                lt = qty * up if qty and up else None
            line_items.append(LineItem(item=item_name, quantity=qty, unit_price=up, line_total=lt))

    totals_el = root.find("totals") or root
    subtotal = _parse_currency(get_text(totals_el, "subtotal"))
    tax_rate = _parse_currency(get_text(totals_el, "tax_rate"))
    tax_amount = _parse_currency(get_text(totals_el, "tax_amount"))
    total = _parse_currency(get_text(totals_el, "total"))

    inv = Invoice(
        invoice_number=normalize_invoice_number(inv_num),
        vendor_name=vendor,
        invoice_date=normalize_date(date_str) if date_str else None,
        due_date=normalize_date(due_str) if due_str else None,
        currency=currency,
        payment_terms=payment_terms,
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        total=total,
    )
    return InvoiceBundle(invoice=inv, line_items=line_items)
