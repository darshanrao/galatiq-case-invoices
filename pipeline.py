"""
LangGraph pipeline wiring all invoice-processing stages.

Graph:
    ingest → validate → approve → pay / reject / queue_for_review

Routing:
    ingest     → retry/reject (on failure) or validate (on success)
    validate   → reject (HARD_FAIL) or approve (passed)
    approve    → pay (APPROVED) | reject (REJECTED) | queue_for_review (PENDING_REVIEW)
    pay        → END
    reject     → END
    queue_for_review → END  (returns status="pending_review"; human resolves via dashboard)
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import ingestion
import inventory_db
import review_queue
import validation
from approval import approve
from llm_extract import LLMConfigurationError
from models import InvoiceState
from payment import pay, reject

from langgraph.graph import END, START, StateGraph

MAX_INGEST_ATTEMPTS = 2

# Module-level callback — set by api.py before each pipeline run
_on_stage_complete: Optional[Callable[[str, dict], None]] = None


def _notify(stage: str, state: dict) -> None:
    """Call the stage callback if one is registered."""
    if _on_stage_complete is not None:
        try:
            _on_stage_complete(stage, state)
        except Exception:
            pass  # Never let callback failures break the pipeline


# ---------------------------------------------------------------------------
# Adapter nodes
# ---------------------------------------------------------------------------

def ingest_node(state: InvoiceState) -> dict[str, Any]:
    """LangGraph node: ingest the invoice file into an InvoiceBundle."""
    audit_log: list[str] = list(state.get("audit_log", []))
    attempts: int = state.get("ingestion_attempts", 0) + 1
    file_path: str = state["file_path"]

    audit_log.append(f"Ingestion attempt {attempts}: {file_path}")

    try:
        bundle = ingestion.ingest_invoice(file_path)
        audit_log.append(f"Ingestion success: {bundle.invoice.invoice_number}")
        result = {
            "invoice": bundle,
            "ingestion_attempts": attempts,
            "ingestion_issues": [],
            "audit_log": audit_log,
        }
        _notify("ingestion", {**state, **result, "ingestion_success": True})
        return result
    except (FileNotFoundError, ingestion.IngestionError, LLMConfigurationError) as exc:
        audit_log.append(f"Ingestion failed (attempt {attempts}): {exc}")
        result = {
            "invoice": None,
            "ingestion_attempts": attempts,
            "ingestion_issues": [str(exc)],
            "audit_log": audit_log,
        }
        _notify("ingestion", {**state, **result, "ingestion_success": False})
        return result
    except Exception as exc:
        audit_log.append(f"Ingestion unexpected error (attempt {attempts}): {exc}")
        result = {
            "invoice": None,
            "ingestion_attempts": attempts,
            "ingestion_issues": [f"Unexpected: {exc}"],
            "audit_log": audit_log,
        }
        _notify("ingestion", {**state, **result, "ingestion_success": False})
        return result


def validate_node(state: InvoiceState) -> dict[str, Any]:
    """LangGraph node: validate the InvoiceBundle against inventory rules."""
    audit_log: list[str] = list(state.get("audit_log", []))
    bundle = state["invoice"]

    result = validation.validate_invoice(
        bundle,
        get_item=inventory_db.get_item,
        is_fraud_item=inventory_db.is_fraud_item,
    )

    hard_count = sum(1 for f in result.flags if f.severity.value == "HARD_FAIL")
    warn_count = sum(1 for f in result.flags if f.severity.value == "WARNING")
    audit_log.append(
        f"Validation {'PASSED' if result.passed else 'FAILED'}: "
        f"{hard_count} HARD_FAIL, {warn_count} WARNING"
    )
    out = {"validation_result": result, "audit_log": audit_log}
    _notify("validation", {**state, **out})
    return out


def queue_for_review_node(state: InvoiceState) -> dict[str, Any]:
    """LangGraph node: store invoice in human review queue and return pending status."""
    audit_log: list[str] = list(state.get("audit_log", []))
    bundle = state.get("invoice")
    ar = state.get("approval_result")

    invoice_number = bundle.invoice.invoice_number if bundle else "unknown"
    vendor = bundle.invoice.vendor_name if bundle else "unknown"
    amount = (bundle.invoice.total or 0.0) if bundle else 0.0

    vr = state.get("validation_result")
    flag_pattern = "|".join(sorted(
        {f.category for f in vr.flags if f.severity.value == "WARNING"}
    )) if vr else ""

    risk_score = ar.risk_score if ar else 0.5
    recommendation = getattr(ar, "llm_recommendation", "REJECT") or "REJECT"
    explanation = ar.final_reasoning if ar else "Requires manual review."

    review_id = review_queue.enqueue(
        file_path=state.get("file_path", ""),
        invoice_number=invoice_number,
        vendor=vendor,
        amount=amount,
        flag_pattern=flag_pattern,
        risk_score=risk_score,
        recommendation=recommendation,
        flag_explanation=explanation,
    )

    audit_log.append(
        f"Queued for human review: id={review_id}, risk={risk_score:.2f}, "
        f"recommendation={recommendation}"
    )

    out = {
        "status": "pending_review",
        "audit_log": audit_log,
        "review_id": review_id,
    }
    _notify("queue_for_review", {**state, **out})
    return out


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def route_after_ingestion(state: InvoiceState) -> str:
    if state.get("invoice") is not None:
        return "validate"
    attempts = state.get("ingestion_attempts", 0)
    if attempts < MAX_INGEST_ATTEMPTS:
        return "ingest"
    return "reject"


def route_after_validation(state: InvoiceState) -> str:
    vr = state.get("validation_result")
    if vr is None or not vr.passed:
        return "reject"
    return "approve"


def route_after_approval(state: InvoiceState) -> str:
    ar = state.get("approval_result")
    if ar is None:
        return "reject"
    if ar.decision == "APPROVED":
        return "pay"
    if ar.decision == "PENDING_REVIEW":
        return "queue_for_review"
    return "reject"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph():
    """Build and compile the LangGraph StateGraph."""
    builder = StateGraph(InvoiceState)

    def approve_node(state: InvoiceState) -> dict[str, Any]:
        result = approve(state)
        _notify("approval", {**state, **result})
        return result

    def pay_node(state: InvoiceState) -> dict[str, Any]:
        result = pay(state)
        _notify("payment", {**state, **result})
        return result

    def reject_node(state: InvoiceState) -> dict[str, Any]:
        result = reject(state)
        _notify("payment", {**state, **result})
        return result

    builder.add_node("ingest", ingest_node)
    builder.add_node("validate", validate_node)
    builder.add_node("approve", approve_node)
    builder.add_node("pay", pay_node)
    builder.add_node("reject", reject_node)
    builder.add_node("queue_for_review", queue_for_review_node)

    builder.add_edge(START, "ingest")

    builder.add_conditional_edges(
        "ingest",
        route_after_ingestion,
        {"validate": "validate", "ingest": "ingest", "reject": "reject"},
    )
    builder.add_conditional_edges(
        "validate",
        route_after_validation,
        {"approve": "approve", "reject": "reject"},
    )
    builder.add_conditional_edges(
        "approve",
        route_after_approval,
        {"pay": "pay", "reject": "reject", "queue_for_review": "queue_for_review"},
    )

    builder.add_edge("pay", END)
    builder.add_edge("reject", END)
    builder.add_edge("queue_for_review", END)

    return builder.compile()


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run(
    file_path: str,
    db_path: str | None = None,
    on_stage_complete: Optional[Callable[[str, dict], None]] = None,
) -> InvoiceState:
    """Run a single invoice through the full pipeline.

    Args:
        file_path:          Path to the invoice file.
        db_path:            Optional path to inventory.db.
        on_stage_complete:  Optional callback called after each stage completes.
                            Signature: callback(stage_name: str, partial_state: dict)
    """
    global _on_stage_complete
    _on_stage_complete = on_stage_complete

    inventory_db.init_inventory_db(db_path)
    initial_state: InvoiceState = {
        "file_path": str(file_path),
        "status": "pending",
        "audit_log": [],
        "ingestion_attempts": 0,
    }
    try:
        return _get_graph().invoke(initial_state)
    finally:
        _on_stage_complete = None
