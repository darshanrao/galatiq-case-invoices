"""
Vision-based invoice extraction using xAI Grok Vision.

Handles:
- Images (JPEG, PNG, TIFF, etc.) — direct vision extraction
- Scanned PDFs — PDF pages converted to images, then vision per page

Uses grok-2-vision-1212 for image understanding.
Requires XAI_API_KEY.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from src.core.models import Invoice, InvoiceBundle, LineItem
from src.core.exceptions import VisionConfigurationError
from src.ingestion.normalizer import normalize_date, normalize_invoice_number, normalize_item_name

logger = logging.getLogger(__name__)

VISION_MODEL = "grok-4-fast-reasoning"  # supports text, image → text
LLM_TIMEOUT = 60
LLM_MAX_RETRIES = 2
LLM_BACKOFF_BASE = 1.0

_RETRYABLE = ("timeout", "rate limit", "429", "503", "502", "connection", "temporary", "overloaded")

_VISION_PROMPT = """Extract invoice data from this invoice image. Return ONLY a valid JSON object.

Expected JSON structure:
{{
  "invoice_number": "string — normalize to INV-XXXX if possible",
  "vendor": "string or {{name, address}}",
  "date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "line_items": [
    {{"item": "string", "quantity": number, "unit_price": number, "line_total": number or null, "note": "string or null"}}
  ],
  "subtotal": number or null,
  "tax_rate": number or null,
  "tax_amount": number or null,
  "total": number or null,
  "shipping": number or null,
  "currency": "USD or actual",
  "payment_terms": "string or null",
  "notes": "string or null",
  "revision": "string or null"
}}

Rules:
- Return ONLY the JSON. No markdown fences, no explanation.
- Extract ALL line items. Shipping/handling go in top-level "shipping", not as line items.
- Use null for missing fields.
"""


def _get_api_key() -> str:
    key = os.getenv("XAI_API_KEY")
    if not key or not str(key).strip():
        raise VisionConfigurationError(
            "XAI_API_KEY required for image/scanned PDF extraction. Set it in .env"
        )
    return key.strip()


def _image_to_base64(path: Path) -> tuple[str, str]:
    """Load image and return (base64_string, mime_type)."""
    import io

    from PIL import Image

    with Image.open(path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        fmt = "JPEG" if img.mode == "RGB" else "PNG"
        img.save(buf, format=fmt, quality=95)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        mime = "image/jpeg" if fmt == "JPEG" else "image/png"
        return b64, mime


def _call_grok_vision(image_data_urls: list[str], prompt: str) -> str:
    """Call Grok Vision API with one or more images. Returns response text."""
    import httpx

    key = _get_api_key()
    # Use OpenAI-compatible format (xAI models support image_url + text)
    content: list[dict] = []
    for url in image_data_urls:
        content.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": "high"},
        })
    content.append({"type": "text", "text": prompt})

    body = {
        "model": VISION_MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
    }

    last_exc: Exception | None = None
    for attempt in range(1 + LLM_MAX_RETRIES):
        try:
            with httpx.Client(timeout=LLM_TIMEOUT) as client:
                r = client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=body,
                )
                r.raise_for_status()
                data = r.json()
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})
                return msg.get("content", "").strip()
        except Exception as exc:
            last_exc = exc
            if attempt < LLM_MAX_RETRIES and any(s in str(exc).lower() for s in _RETRYABLE):
                wait = LLM_BACKOFF_BASE * (2**attempt)
                logger.warning("Vision API retry %s/%s after %s", attempt + 1, LLM_MAX_RETRIES, exc)
                time.sleep(wait)
            else:
                raise
    raise last_exc  # type: ignore[misc]


def _parse_vision_response(raw: str) -> InvoiceBundle:
    """Parse JSON from vision response into InvoiceBundle."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw.strip())
    data = json.loads(raw)

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

    def _curr(v):
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    date_raw = data.get("date")
    due_raw = data.get("due_date")
    revision_raw = data.get("revision")
    revision = str(revision_raw).strip() if revision_raw and str(revision_raw).strip() else None
    notes_raw = data.get("notes")
    notes = str(notes_raw).strip() if notes_raw and str(notes_raw).strip() else None

    inv = Invoice(
        invoice_number=normalize_invoice_number(str(data.get("invoice_number") or "")),
        vendor_name=vendor_name,
        invoice_date=normalize_date(str(date_raw)) if date_raw else None,
        due_date=normalize_date(str(due_raw)) if due_raw else None,
        vendor_address=vendor_address,
        revision=revision,
        currency=str(data.get("currency") or "USD"),
        payment_terms=str(data.get("payment_terms")) if data.get("payment_terms") else None,
        subtotal=_curr(data.get("subtotal")),
        tax_rate=_curr(data.get("tax_rate")),
        tax_amount=_curr(data.get("tax_amount")),
        total=_curr(data.get("total")),
        shipping=_curr(data.get("shipping")),
        notes=notes,
    )
    return InvoiceBundle(invoice=inv, line_items=line_items)


def extract_invoice_from_image(path: str | Path) -> InvoiceBundle | None:
    """Extract invoice from a single image file (JPEG, PNG, etc.)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    b64, mime = _image_to_base64(path)
    url = f"data:{mime};base64,{b64}"

    try:
        raw = _call_grok_vision([url], _VISION_PROMPT)
        return _parse_vision_response(raw)
    except json.JSONDecodeError as e:
        logger.warning("Vision returned invalid JSON: %s", e)
        return None


def extract_invoice_from_images(image_paths: list[str | Path]) -> InvoiceBundle | None:
    """Extract invoice from multiple images (e.g. multi-page scanned PDF)."""
    urls: list[str] = []
    for p in image_paths:
        p = Path(p)
        if not p.exists():
            continue
        b64, mime = _image_to_base64(p)
        urls.append(f"data:{mime};base64,{b64}")

    if not urls:
        return None

    try:
        raw = _call_grok_vision(urls, _VISION_PROMPT)
        return _parse_vision_response(raw)
    except json.JSONDecodeError as e:
        logger.warning("Vision returned invalid JSON: %s", e)
        return None
