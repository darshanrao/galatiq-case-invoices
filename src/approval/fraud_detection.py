"""Fraud indicator detection for the approval stage."""

from __future__ import annotations

from src.core.models import InvoiceState

_SUSPICIOUS_VENDOR_KEYWORDS = frozenset({
    "urgent", "rush", "express", "immediate", "asap", "priority", "emergency",
    "wire", "offshore", "anonymous",
})

_URGENCY_PHRASES = frozenset({
    "pay immediately", "urgent payment", "wire transfer", "send now",
    "process immediately", "rush payment", "must pay today",
})


def count_fraud_indicators(state: InvoiceState) -> int:
    """Count fraud-risk signals in the invoice (0–4 range)."""
    bundle = state.get("invoice")
    if bundle is None:
        return 0
    inv = bundle.invoice
    count = 0
    vendor_lower = (inv.vendor_name or "").lower()
    if any(kw in vendor_lower for kw in _SUSPICIOUS_VENDOR_KEYWORDS):
        count += 1
    notes_lower = (inv.notes or "").lower()
    if any(phrase in notes_lower for phrase in _URGENCY_PHRASES):
        count += 1
    if inv.due_date is None:
        count += 1
    if inv.total is not None and inv.total > 50_000:
        count += 1
    return count
