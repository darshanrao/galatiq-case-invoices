"""
Text normalizer for OCR cleanup and field normalization.

All functions are pure Python (deterministic) — no LLM calls.
"""

import re
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# normalize_text — OCR artifact cleanup
# ---------------------------------------------------------------------------

_NUMERIC_TOKEN_PATTERN = re.compile(r"(?<![A-Za-z])[0-9,.O]+(?![A-Za-z])")


def _replace_o_in_numeric(m: re.Match[str]) -> str:
    token = m.group(0)
    if re.search(r"\d", token):
        return token.replace("O", "0")
    return token


def normalize_text(raw: str) -> str:
    """Replace letter O with digit 0 in numeric contexts only (OCR cleanup)."""
    return _NUMERIC_TOKEN_PATTERN.sub(_replace_o_in_numeric, raw)


# ---------------------------------------------------------------------------
# normalize_item_name — collapse spaces
# ---------------------------------------------------------------------------


def normalize_item_name(name: Optional[str]) -> str:
    """Collapse internal spaces: 'Widget A' -> 'WidgetA', 'Gadget X' -> 'GadgetX'. Returns '' for None."""
    if name is None:
        return ""
    return name.strip().replace(" ", "")


# ---------------------------------------------------------------------------
# normalize_date — parse flexible date strings to ISO YYYY-MM-DD
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d-%b-%Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
]


def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """Parse date string and return ISO YYYY-MM-DD, or None if unparseable. Handles non-string (e.g. int) via str()."""
    if date_str is None:
        return None
    cleaned = str(date_str).strip()
    if not cleaned:
        return None
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# normalize_invoice_number — standardise to INV-XXXX
# ---------------------------------------------------------------------------

_BARE_NUMBER_PATTERN = re.compile(r"^\d+$")
_INV_SPACE_PATTERN = re.compile(r"^([A-Za-z]+)[\s_](\d+)$")


def normalize_invoice_number(raw_id: Optional[str]) -> str:
    """Normalise invoice number to INV-XXXX format. Returns '' for None."""
    if raw_id is None:
        return ""
    cleaned = raw_id.strip()

    if re.match(r"^[A-Za-z]+-\d+$", cleaned):
        prefix, number = cleaned.split("-", 1)
        return f"{prefix.upper()}-{number}"

    if _BARE_NUMBER_PATTERN.match(cleaned):
        return f"INV-{cleaned}"

    m = _INV_SPACE_PATTERN.match(cleaned)
    if m:
        prefix, number = m.group(1), m.group(2)
        return f"{prefix.upper()}-{number}"

    return cleaned


# ---------------------------------------------------------------------------
# normalize_tax_rate — percentage (5) to decimal (0.05)
# ---------------------------------------------------------------------------


def normalize_tax_rate(val: Optional[float]) -> Optional[float]:
    """Convert percentage form (5, 6, 1) to decimal (0.05, 0.06, 0.01). Accepts str (e.g. '8') via float()."""
    if val is None:
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return val
    if v == 0:
        return 0.0
    if 0 < v < 1:
        return v  # already decimal
    if 1 <= v <= 100:
        return v / 100  # percentage: 1->0.01, 5->0.05, 100->1.0
    return v
