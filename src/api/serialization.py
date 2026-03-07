"""Serialization helpers for the API layer."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass


def _safe_serialize(obj):
    """Recursively convert dataclasses / enums to JSON-serializable dicts."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _safe_serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_safe_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if hasattr(obj, "value"):  # Enum
        return obj.value
    return obj


def _stage_data_from_state(state: dict, stage: str) -> dict:
    """Extract serializable data for a given stage from pipeline state."""
    if stage == "ingestion":
        bundle = state.get("invoice")
        if bundle is None:
            return {
                "status": "failed",
                "issues": state.get("ingestion_issues", []),
            }
        inv = bundle.invoice
        return {
            "status": "success",
            "vendor": inv.vendor_name,
            "amount": inv.total,
            "due_date": inv.due_date,
            "invoice_number": inv.invoice_number,
            "line_items": _safe_serialize(bundle.line_items),
            "invoice_date": inv.invoice_date,
        }

    if stage == "validation":
        vr = state.get("validation_result")
        if vr is None:
            return {}
        return {
            "passed": vr.passed,
            "flags": _safe_serialize(vr.flags),
            "item_matches": _safe_serialize(vr.item_matches),
            "arithmetic": _safe_serialize(vr.arithmetic_check),
        }

    if stage == "approval":
        ar = state.get("approval_result")
        if ar is None:
            return {}
        return {
            "decision": ar.decision,
            "risk_score": ar.risk_score,
            "reasoning": ar.final_reasoning,
            "prosecution": ar.prosecution_argument,
            "defense": ar.defense_argument,
            "source": ar.decision_source,
            "llm_recommendation": ar.llm_recommendation,
        }

    if stage == "payment":
        pr = state.get("payment_result")
        if pr is None:
            return {}
        return _safe_serialize(pr)

    return {}
