"""
Payment stage for the invoice processing pipeline.

pay()    — executes mock payment for approved invoices.
reject() — builds structured rejection for invoices that failed at any stage.
"""

from __future__ import annotations

from typing import Any

from src.core.models import InvoiceState, PaymentResult


def mock_payment(vendor: str, amount: float) -> dict:
    """Simulate sending a payment. In production this would call a payment API."""
    print(f"  [PAYMENT] Paid ${amount:,.2f} to {vendor}")
    return {"status": "success"}


def pay(state: InvoiceState) -> dict[str, Any]:
    """LangGraph node: execute mock payment for an approved invoice."""
    audit_log: list[str] = list(state.get("audit_log", []))
    bundle = state.get("invoice")

    vendor = bundle.invoice.vendor_name if bundle else "unknown"
    amount = (bundle.invoice.total or 0.0) if bundle else 0.0

    mock_payment(vendor, amount)
    audit_log.append(f"Payment: paid ${amount:,.2f} to {vendor}")

    result = PaymentResult(
        status="paid",
        vendor=vendor,
        amount=amount,
    )
    return {"payment_result": result, "status": "approved", "audit_log": audit_log}


def reject(state: InvoiceState) -> dict[str, Any]:
    """LangGraph node: build structured rejection regardless of which stage failed."""
    audit_log: list[str] = list(state.get("audit_log", []))
    bundle = state.get("invoice")

    vendor = bundle.invoice.vendor_name if bundle else "unknown"
    amount = (bundle.invoice.total or 0.0) if bundle else 0.0

    rejection_stage: str
    rejection_reason: str

    ingestion_issues = state.get("ingestion_issues") or []
    if state.get("invoice") is None and ingestion_issues:
        rejection_stage = "ingestion"
        rejection_reason = "; ".join(ingestion_issues) or "Invoice could not be parsed."
    elif state.get("validation_result") is not None and not state["validation_result"].passed:
        rejection_stage = "validation"
        hard_flags = [
            f.message
            for f in state["validation_result"].flags
            if f.severity.value == "HARD_FAIL"
        ]
        rejection_reason = "; ".join(hard_flags) if hard_flags else "Validation failed."
    elif state.get("approval_result") is not None and state["approval_result"].decision == "REJECTED":
        rejection_stage = "approval"
        rejection_reason = state["approval_result"].final_reasoning
    else:
        rejection_stage = "unknown"
        rejection_reason = "Invoice rejected — cause undetermined."

    audit_log.append(f"Rejection at {rejection_stage}: {rejection_reason}")

    result = PaymentResult(
        status="rejected",
        vendor=vendor,
        amount=amount,
        rejection_reason=rejection_reason,
        rejection_stage=rejection_stage,
    )
    return {"payment_result": result, "status": "rejected", "audit_log": audit_log}
