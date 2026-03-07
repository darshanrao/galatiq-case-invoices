"""Ingestion service: orchestrates extraction from various invoice formats."""

from pathlib import Path

from src.core.models import Invoice, InvoiceBundle, LineItem
from src.core.exceptions import IngestionError
from src.ingestion.normalizer import (
    normalize_date,
    normalize_invoice_number,
    normalize_item_name,
    normalize_tax_rate,
)
from src.ingestion.parsers import parse_json, parse_csv, parse_xml, parse_txt
from src.ingestion.read_file import read_invoice_file


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


def ingest_invoice(path: str | Path) -> InvoiceBundle:
    """Extract structured invoice data. Deterministic first, then LLM if critical fields missing."""
    from src.ingestion.llm_extract import extract_invoice_with_llm

    raw_content, file_format = read_invoice_file(path)

    bundle = None
    try:
        if file_format == "json":
            bundle = parse_json(raw_content)
        elif file_format == "csv":
            bundle = parse_csv(raw_content)
        elif file_format == "xml":
            bundle = parse_xml(raw_content)
        elif file_format == "txt":
            bundle = parse_txt(raw_content)
    except Exception:
        bundle = None

    missing = get_missing_critical_fields(bundle) if bundle else ["invoice_number", "line_items", "total", "date", "due_date", "currency", "payment_terms"]

    FREEFORM_FORMATS = {"txt", "pdf"}
    is_freeform = file_format in FREEFORM_FORMATS

    core_missing = {"invoice_number", "line_items", "total"}
    level1_has_minimal = not core_missing.intersection(missing) and not is_freeform

    if not level1_has_minimal:
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
