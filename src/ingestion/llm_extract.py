"""
LLM-based invoice extraction for the tiered pipeline.

Requires XAI_API_KEY. Uses xAI Grok (grok-3-mini) to extract structured invoice
data from unstructured text when deterministic parsers fail or return incomplete data.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from src.core.models import Invoice, InvoiceBundle, LineItem
from src.core.exceptions import LLMConfigurationError
from src.ingestion.normalizer import normalize_date, normalize_invoice_number, normalize_item_name, normalize_text

logger = logging.getLogger(__name__)


# Retry configuration
LLM_TIMEOUT = 30
LLM_MAX_RETRIES = 2
LLM_BACKOFF_BASE = 1.0

_RETRYABLE_SUBSTRINGS = (
    "timeout",
    "rate limit",
    "rate_limit",
    "429",
    "503",
    "502",
    "connection",
    "temporary",
    "server error",
    "overloaded",
)

_LLM_PROMPT_TEMPLATE = """\
Extract invoice data from the text below and return ONLY a valid JSON object.

Expected JSON structure (canonical form):
{{
  "invoice_number": "string — normalize to INV-XXXX format if possible",
  "vendor": "string or {{name, address}} — company name; address if present",
  "date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "line_items": [
    {{
      "item": "string — canonical product name (e.g. WidgetA); use item or item_name",
      "quantity": number,
      "unit_price": number,
      "line_total": number or null,
      "note": "string or null — e.g. Volume discount, Rush order"
    }}
  ],
  "subtotal": number or null,
  "tax_rate": number or null,
  "tax_amount": number or null,
  "total": number or null,
  "shipping": number or null — separate shipping/freight amount if stated; do NOT put as line item",
  "currency": "USD — or actual currency if stated",
  "payment_terms": "string or null",
  "notes": "string or null — invoice-level notes",
  "revision": "string or null — e.g. R1 if revised"
}}

Rules:
- Return ONLY the JSON object. No explanation, no markdown fences.
- Extract ALL physical product/goods line items. Shipping, handling, freight, delivery are NOT line items — extract them as the top-level "shipping" field if present.
- item: use canonical product name only (e.g. WidgetA). Strip parenthetical descriptions like "(rush order)".
- If a field is absent or unparseable, use null (not string "null").
{missing_fields_hint}
Invoice text:
{text}
"""

_LLM_MISSING_FIELDS_HINT = """

IMPORTANT: A previous (deterministic) extraction succeeded but the following critical fields were missing or null: {missing_list}.
Pay special attention to extracting these from the text below. Return a complete JSON with these fields filled where the source text allows.
"""


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in _RETRYABLE_SUBSTRINGS)


def get_llm() -> Any:
    """Return xAI Grok ChatOpenAI. Raises LLMConfigurationError if XAI_API_KEY is not set."""
    xai_key = os.getenv("XAI_API_KEY")
    if not xai_key or not str(xai_key).strip():
        raise LLMConfigurationError(
            "XAI_API_KEY is required for LLM extraction. "
            "Set it in .env or environment for TXT/PDF and fallback extraction."
        )
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model="grok-3-mini",
        api_key=xai_key,
        base_url="https://api.x.ai/v1",
        timeout=LLM_TIMEOUT,
    )


def invoke_with_retry(
    llm: Any,
    prompt: str,
    *,
    max_retries: int = LLM_MAX_RETRIES,
    backoff_base: float = LLM_BACKOFF_BASE,
    audit_log: list[str] | None = None,
) -> Any:
    """Invoke LLM with retry and exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(1 + max_retries):
        try:
            return llm.invoke(prompt)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries and _is_retryable(exc):
                wait = backoff_base * (2**attempt)
                logger.warning(
                    "LLM invoke retry",
                    extra={"attempt": attempt + 1, "max_retries": max_retries, "wait_seconds": wait},
                )
                if audit_log is not None:
                    audit_log.append(f"LLM: Retry {attempt + 1}/{max_retries} after {exc}")
                time.sleep(wait)
            else:
                raise
    raise last_exc  # type: ignore[misc]


def _parse_llm_response_to_bundle(raw: str) -> InvoiceBundle:
    """Parse JSON from LLM response and build InvoiceBundle (canonical form)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw.strip())

    data: dict = json.loads(raw)

    vendor = data.get("vendor")
    vendor_name = vendor.get("name", "") if isinstance(vendor, dict) else str(vendor or "")
    vendor_address = vendor.get("address") if isinstance(vendor, dict) else None
    if vendor_address is not None:
        vendor_address = str(vendor_address).strip() or None

    line_items: list[LineItem] = []
    for li in data.get("line_items", []):
        item_raw = li.get("item") or li.get("item_name") or ""
        item = normalize_item_name(str(item_raw))
        qty_val = li.get("quantity")
        qty = int(qty_val) if isinstance(qty_val, int) else int(float(qty_val or 0))
        up = float(li.get("unit_price") or 0)
        lt = li.get("line_total")
        lt = float(lt) if lt is not None else (qty * up if qty and up else None)
        note_raw = li.get("note")
        note = str(note_raw).strip() if note_raw and str(note_raw).strip() else None
        line_items.append(LineItem(item=item, quantity=qty, unit_price=up, line_total=lt, note=note))

    date_raw = data.get("date")
    due_date_raw = data.get("due_date")
    revision_raw = data.get("revision")
    revision = str(revision_raw).strip() if revision_raw and str(revision_raw).strip() else None
    notes_raw = data.get("notes")
    notes = str(notes_raw).strip() if notes_raw and str(notes_raw).strip() else None
    shipping_raw = data.get("shipping")
    shipping = float(shipping_raw) if shipping_raw is not None else None

    inv = Invoice(
        invoice_number=normalize_invoice_number(str(data.get("invoice_number") or "")),
        vendor_name=vendor_name,
        invoice_date=normalize_date(str(date_raw)) if date_raw else None,
        due_date=normalize_date(str(due_date_raw)) if due_date_raw else None,
        vendor_address=vendor_address,
        revision=revision,
        currency=str(data.get("currency") or "USD"),
        payment_terms=str(data.get("payment_terms")) if data.get("payment_terms") else None,
        subtotal=float(data["subtotal"]) if data.get("subtotal") is not None else None,
        tax_rate=float(data["tax_rate"]) if data.get("tax_rate") is not None else None,
        tax_amount=float(data["tax_amount"]) if data.get("tax_amount") is not None else None,
        total=float(data["total"]) if data.get("total") is not None else None,
        shipping=shipping,
        notes=notes,
    )
    return InvoiceBundle(invoice=inv, line_items=line_items)


def extract_invoice_with_llm(
    raw_content: str,
    missing_critical_fields: list[str] | None = None,
) -> InvoiceBundle | None:
    """Extract invoice from unstructured text via LLM. Returns None on parse failure.

    If missing_critical_fields is provided (e.g. from a previous deterministic parse),
    the prompt tells the LLM to focus on filling those fields for better extraction.
    """
    cleaned = normalize_text(raw_content)
    missing_hint = ""
    if missing_critical_fields:
        missing_list = ", ".join(missing_critical_fields)
        missing_hint = _LLM_MISSING_FIELDS_HINT.format(missing_list=missing_list)
    prompt = _LLM_PROMPT_TEMPLATE.format(
        text=cleaned,
        missing_fields_hint=missing_hint,
    )
    llm = get_llm()

    try:
        response = invoke_with_retry(llm, prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return _parse_llm_response_to_bundle(content)
    except json.JSONDecodeError as e:
        logger.warning("LLM returned invalid JSON: %s", e)
        return None
    except Exception as e:
        logger.error("LLM extraction failed: %s", e)
        raise
