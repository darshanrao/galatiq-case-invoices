"""Ingestion module: extract structured invoice data from various file formats.

EXTRACTION FLOW (tiered, production-oriented):
------------------------------------------------
1. Read: read_invoice_file(path) -> (raw_content, file_format)
   - Supports: .json, .csv, .xml, .txt, .pdf (PDF via pdfplumber)

2. Level 1 - Deterministic parsers:
   - JSON: _parse_json() - structured; supports item/item_name, nested vendor
   - CSV: _parse_csv() - key-value or row-per-line formats
   - XML: _parse_xml() - header, line_items, totals structure
   - TXT: _parse_txt() - regex patterns for common invoice layouts
   - All apply normalizer (item names, dates, invoice numbers)

3. Validation: get_missing_critical_fields(bundle) — single source of what failed
   - Unusable if invoice_number or line_items missing → LLM full extraction
   - Usable but other fields missing → LLM with failure list for targeted extraction

4. LLM fallback (when minimal data missing, or when other critical fields missing):
   - extract_invoice_with_llm(raw_content) via xAI Grok
   - Requires XAI_API_KEY (no LocalMockLLM in production)
   - Prompt asks for JSON; response stripped of markdown, parsed, normalizer applied

5. Final: apply_normalizer(bundle) and return
   - If still incomplete after Level 2: raise IngestionError
"""

import csv
import json
import re
import xml.etree.ElementTree as ET
from io import StringIO
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from models import Invoice, InvoiceBundle, LineItem
from normalizer import normalize_date, normalize_invoice_number, normalize_item_name, normalize_tax_rate


class IngestionError(Exception):
    """Raised when invoice extraction fails or validation gate rejects incomplete data."""


# Critical fields for business validation (invoice_number, total, line items, date, due_date, currency, payment_terms)
def get_missing_critical_fields(bundle: InvoiceBundle) -> list[str]:
    """Return list of critical field names that are null or missing."""
    if not bundle:
        return ["invoice_number", "total", "line_items", "date", "due_date", "currency", "payment_terms"]
    inv = bundle.invoice
    missing: list[str] = []
    if not (inv.invoice_number or "").strip():
        missing.append("invoice_number")
    if inv.total is None:
        missing.append("total")
    if not bundle.line_items:
        missing.append("line_items")
    else:
        for i, li in enumerate(bundle.line_items):
            if not (li.item or "").strip():
                missing.append(f"line_items[{i}].item")
            if li.quantity is None:
                missing.append(f"line_items[{i}].quantity")
            if li.unit_price is None:
                missing.append(f"line_items[{i}].unit_price")
    if inv.invoice_date is None:
        missing.append("date")
    if inv.due_date is None:
        missing.append("due_date")
    if not (inv.currency or "").strip():
        missing.append("currency")
    if inv.payment_terms is None or (isinstance(inv.payment_terms, str) and not inv.payment_terms.strip()):
        missing.append("payment_terms")
    return missing


def to_canonical_dict(bundle: InvoiceBundle) -> dict:
    """Convert InvoiceBundle to canonical normalized JSON structure."""
    inv = bundle.invoice
    line_items = [
        {
            "item": li.item,
            "quantity": li.quantity,
            "unit_price": round(li.unit_price, 2),
            "line_total": round(li.line_total, 2) if li.line_total is not None else None,
            "note": li.note,
        }
        for li in bundle.line_items
    ]
    return {
        "invoice_number": inv.invoice_number,
        "vendor_name": inv.vendor_name or None,
        "vendor_address": inv.vendor_address,
        "date": inv.invoice_date,
        "due_date": inv.due_date,
        "line_items": line_items,
        "subtotal": round(inv.subtotal, 2) if inv.subtotal is not None else None,
        "tax_rate": inv.tax_rate,
        "tax_amount": round(inv.tax_amount, 2) if inv.tax_amount is not None else None,
        "total": round(inv.total, 2) if inv.total is not None else None,
        "shipping": round(inv.shipping, 2) if inv.shipping is not None else None,
        "currency": inv.currency or "USD",
        "payment_terms": (str(inv.payment_terms).strip() or None) if inv.payment_terms is not None else None,
        "notes": inv.notes,
        "revision": inv.revision,
    }


def apply_normalizer(bundle: InvoiceBundle) -> InvoiceBundle:
    """Re-apply normalizer to bundle fields for consistency."""
    inv = bundle.invoice
    normalized_inv = Invoice(
        invoice_number=normalize_invoice_number(inv.invoice_number),
        vendor_name=inv.vendor_name,
        invoice_date=normalize_date(inv.invoice_date) if inv.invoice_date else None,
        due_date=normalize_date(inv.due_date) if inv.due_date else None,
        vendor_address=inv.vendor_address,
        revision=inv.revision,
        currency=inv.currency,
        payment_terms=(str(inv.payment_terms).strip() or None) if inv.payment_terms is not None else None,
        subtotal=inv.subtotal,
        tax_rate=normalize_tax_rate(inv.tax_rate),
        tax_amount=inv.tax_amount,
        total=inv.total,
        shipping=inv.shipping,
        notes=inv.notes,
    )
    normalized_items = [
        LineItem(
            item=normalize_item_name(li.item),
            quantity=li.quantity,
            unit_price=li.unit_price,
            line_total=li.line_total,
            note=li.note,
        )
        for li in bundle.line_items
    ]
    return InvoiceBundle(invoice=normalized_inv, line_items=normalized_items)


def _parse_currency(val: str | float | None) -> float | None:
    """Parse a currency string like '$5,000.00' or number to float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "")
    m = re.search(r"[\d.-]+", s)
    return float(m.group()) if m else None


def _parse_int(val: str | int | None) -> int | None:
    """Parse quantity to int."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    m = re.search(r"-?\d+", str(val))
    return int(m.group()) if m else None


def _parse_json(content: str) -> InvoiceBundle:
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


def _parse_csv(content: str) -> InvoiceBundle:
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


def _parse_xml(content: str) -> InvoiceBundle:
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


def _parse_txt(content: str) -> InvoiceBundle:
    """Best-effort extraction from freeform TXT/PDF text.

    Philosophy: only extract what simple labeled-field regex is genuinely reliable
    for (vendor name, invoice number). Everything else — line items, totals, dates,
    taxes, shipping — has too many real-world format variants to regex reliably.
    Missing fields are flagged via get_missing_critical_fields() and the LLM fills them.

    What regex IS reliable for here:
      - Vendor: almost always "Vendor: <name>" or "FROM: <name>" on its own line
      - Invoice number: almost always "Invoice #:", "Invoice Number:", "INV NO:" etc.

    What regex is NOT reliable for (left to LLM):
      - Line items: infinite layout variation (tabular, bulleted, inline, mixed)
      - Totals / subtotals / tax / shipping: label names vary widely ("Amount Due",
        "Balance Due", "Grand Total", "VAT", "GST", "S&H", etc.) and values can be
        confused with line item amounts (as the Subtotal/TOTAL bug demonstrated)
      - Dates: label names vary ("Invoice Date", "Issued", "Date Issued", etc.)
      - Payment terms: free-text ("Net 30", "Due on receipt", "30 days", etc.)
    """
    text = content

    # Vendor — labeled field, label is nearly universal
    v_match = re.search(
        r"(?:^|\n)\s*(?:Vendor|Vndr|Supplier|FROM|Bill\s*From|Issued\s*By):\s*(.+)",
        text,
        re.IGNORECASE,
    )
    vendor_name = v_match.group(1).strip() if v_match else ""

    # Invoice number — labeled field with well-known labels
    inv_match = re.search(
        r"(?:Invoice\s*(?:Number|No\.?|#|ID)?|Inv\.?\s*#?|INV\s*NO\.?)[:# ]\s*([A-Za-z0-9][A-Za-z0-9\s\-/]+?)(?:\n|$)",
        text,
        re.IGNORECASE,
    )
    inv_number = inv_match.group(1).strip().replace(" ", "") if inv_match else ""

    # Return a minimal bundle — LLM will fill in everything else
    inv = Invoice(
        invoice_number=normalize_invoice_number(inv_number) if inv_number else "",
        vendor_name=vendor_name,
    )
    return InvoiceBundle(invoice=inv, line_items=[])


def ingest_invoice(path: str | Path) -> InvoiceBundle:
    """Extract structured invoice data. Deterministic first, then LLM if critical fields missing.
    Uses get_missing_critical_fields as the single check; LLM gets the failure list for better extraction.
    """
    from read_file import read_invoice_file
    from llm_extract import extract_invoice_with_llm

    raw_content, file_format = read_invoice_file(path)

    bundle = None
    try:
        if file_format == "json":
            bundle = _parse_json(raw_content)
        elif file_format == "csv":
            bundle = _parse_csv(raw_content)
        elif file_format == "xml":
            bundle = _parse_xml(raw_content)
        elif file_format == "txt":
            bundle = _parse_txt(raw_content)
    except Exception:
        bundle = None

    missing = get_missing_critical_fields(bundle) if bundle else ["invoice_number", "line_items", "total", "date", "due_date", "currency", "payment_terms"]

    # Determine whether Level 1 produced usable minimal data.
    # For structured formats (JSON/CSV/XML), trust the parser — LLM only if fields missing.
    # For freeform (TXT/PDF), the parser intentionally returns a stub; always send to LLM.
    FREEFORM_FORMATS = {"txt", "pdf"}
    is_freeform = file_format in FREEFORM_FORMATS

    # Minimum bar: invoice_number + line_items + total must all be present.
    # A regex that grabs some-but-not-all line items or misreads totals is worse than
    # no result — the LLM should own the full extraction in those cases.
    core_missing = {"invoice_number", "line_items", "total"}
    level1_has_minimal = not core_missing.intersection(missing) and not is_freeform

    if not level1_has_minimal:
        # Full LLM extraction — Level 1 gave nothing usable, or this is a freeform file.
        # Pass any stub data the parser did extract as hints (vendor, inv number).
        hints = missing if (bundle and not is_freeform) else None
        try:
            llm_bundle = extract_invoice_with_llm(raw_content, missing_critical_fields=hints)
            if llm_bundle:
                llm_missing = get_missing_critical_fields(llm_bundle)
                if "invoice_number" not in llm_missing and "line_items" not in llm_missing:
                    bundle = llm_bundle
                    missing = llm_missing
        except Exception:
            pass
    elif missing:
        # Level 1 gave invoice_number + line_items + total but some secondary fields absent.
        # Targeted LLM pass with the specific failure list.
        try:
            llm_bundle = extract_invoice_with_llm(raw_content, missing_critical_fields=missing)
            if llm_bundle:
                llm_missing = get_missing_critical_fields(llm_bundle)
                if "invoice_number" not in llm_missing and "line_items" not in llm_missing:
                    if len(llm_missing) < len(missing):
                        bundle = llm_bundle
                        missing = llm_missing
        except Exception:
            pass

    if not bundle or "invoice_number" in missing or "line_items" in missing:
        raise IngestionError("Could not extract usable invoice (need invoice_number and line_items)")

    return apply_normalizer(bundle)
