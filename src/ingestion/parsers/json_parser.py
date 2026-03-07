"""JSON invoice parser."""

import json
import re

from src.core.models import Invoice, InvoiceBundle, LineItem
from src.ingestion.normalizer import normalize_date, normalize_invoice_number, normalize_item_name

from .utils import _parse_currency, _parse_int


def parse_json(content: str) -> InvoiceBundle:
    """Parse JSON invoice. Supports item/item_name, nested vendor, revision, notes."""
    data = json.loads(content)

    vendor = data.get("vendor") or data.get("vendor_name")
    vendor_name = vendor.get("name", "") if isinstance(vendor, dict) else str(vendor or "")
    vendor_address = vendor.get("address") if isinstance(vendor, dict) else None
    if vendor_address is not None:
        vendor_address = str(vendor_address).strip() or None

    line_items: list[LineItem] = []
    for li in data.get("line_items", []):
        item_raw = li.get("item_name") or li.get("item") or ""
        item = normalize_item_name(str(item_raw))
        qty = _parse_int(li.get("quantity"))
        if qty is None:
            qty = 0
        up = _parse_currency(li.get("unit_price")) or 0.0
        lt = _parse_currency(li.get("amount") or li.get("line_total"))
        if lt is None:
            lt = qty * up if up else None
        note_raw = li.get("note")
        note = str(note_raw).strip() if note_raw and str(note_raw).strip() else None
        line_items.append(LineItem(item=item, quantity=qty, unit_price=up, line_total=lt, note=note))

    inv_num_raw = str(data.get("invoice_number", ""))
    date_raw = data.get("date")
    due_raw = data.get("due_date")
    revision_raw = data.get("revision")
    revision = str(revision_raw).strip() if revision_raw is not None and str(revision_raw).strip() else None

    notes_raw = data.get("notes")
    notes = str(notes_raw).strip() if notes_raw and str(notes_raw).strip() else None
    shipping = _parse_currency(data.get("shipping"))

    inv = Invoice(
        invoice_number=normalize_invoice_number(inv_num_raw) if inv_num_raw else "",
        vendor_name=vendor_name,
        invoice_date=normalize_date(str(date_raw)) if date_raw is not None else None,
        due_date=normalize_date(str(due_raw)) if due_raw is not None else None,
        vendor_address=vendor_address,
        revision=revision,
        currency=data.get("currency", "USD"),
        payment_terms=data.get("payment_terms"),
        subtotal=_parse_currency(data.get("subtotal")),
        tax_rate=_parse_currency(data.get("tax_rate")),
        tax_amount=_parse_currency(data.get("tax_amount")),
        total=_parse_currency(data.get("total")),
        shipping=shipping,
        notes=notes,
    )
    return InvoiceBundle(invoice=inv, line_items=line_items)
