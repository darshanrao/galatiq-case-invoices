"""TXT/PDF invoice parser (best-effort regex extraction)."""

import re

from src.core.models import Invoice, InvoiceBundle
from src.ingestion.normalizer import normalize_invoice_number


def parse_txt(content: str) -> InvoiceBundle:
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
