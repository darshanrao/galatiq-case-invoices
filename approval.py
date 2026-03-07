"""
Approval stage for the invoice processing pipeline.

Tier 1 — Fraud auto-reject (deterministic, no LLM):
    2+ fraud indicators → REJECTED immediately.

Tier 2 — Deterministic rules (no LLM):
    - currency_mismatch flag → REJECTED
    - zero flags + zero fraud → APPROVED
    - only minor warnings (arithmetic_mismatch, duplicate_invoice) + ≤1 fraud → APPROVED

Tier 2.5 — Precedent self-correction:
    - Look up flag_pattern in precedent_db.
    - count ≥ 3 (all same decision) → auto-decide, source="learned_precedent".

Tier 3 — Single structured LLM risk-scoring call:
    - One call returns: risk_score (0–1), recommendation (APPROVE|REJECT), plain-English explanation.
    - Decision is PENDING_REVIEW — routed to human review queue, not auto-decided.
    - Human decision is stored via record_human_override() → feeds Tier 2.5 for future runs.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import precedent_db
from llm_extract import get_llm, invoke_with_retry
from models import ApprovalResult, InvoiceState, Severity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fraud indicator helpers
# ---------------------------------------------------------------------------

_SUSPICIOUS_VENDOR_KEYWORDS = frozenset({
    "urgent", "rush", "express", "immediate", "asap", "priority", "emergency",
    "wire", "offshore", "anonymous",
})

_URGENCY_PHRASES = frozenset({
    "pay immediately", "urgent payment", "wire transfer", "send now",
    "process immediately", "rush payment", "must pay today",
})


def _count_fraud_indicators(state: InvoiceState) -> int:
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


def _warning_flag_pattern(state: InvoiceState) -> str:
    """Compute the flag_pattern key for precedent lookup (WARNING flags only)."""
    vr = state.get("validation_result")
    if vr is None:
        return ""
    return "|".join(sorted({f.category for f in vr.flags if f.severity == Severity.WARNING}))


def _warning_categories(state: InvoiceState) -> set[str]:
    vr = state.get("validation_result")
    if vr is None:
        return set()
    return {f.category for f in vr.flags if f.severity == Severity.WARNING}


# ---------------------------------------------------------------------------
# Single structured LLM risk-scoring call
# ---------------------------------------------------------------------------

_RISK_SCORE_PROMPT = """\
You are a financial risk analyst reviewing an invoice before human VP approval.
Your job is to assess risk and explain the flags in plain business English.

Invoice details:
  Vendor: {vendor}
  Total: ${total}
  Currency: {currency}
  Due date: {due_date}
  Flags detected: {flags}
  Invoice notes: {notes}

Respond ONLY with a JSON object — no markdown fences, no extra text:
{{
  "risk_score": <float 0.0 to 1.0, where 1.0 = very high risk>,
  "recommendation": "APPROVE" or "REJECT",
  "explanation": "<one or two plain-English sentences a non-technical reviewer can act on>"
}}

Scoring guidance:
- 0.0–0.3: routine issues, likely safe to approve
- 0.4–0.6: notable concerns, human judgment needed
- 0.7–1.0: significant risk, lean toward rejection
"""


def _llm_risk_score(state: InvoiceState) -> dict:
    """Single LLM call: returns risk_score, recommendation, explanation."""
    bundle = state.get("invoice")
    vr = state.get("validation_result")

    inv = bundle.invoice if bundle else None
    flag_strs = ", ".join(f.category for f in vr.flags) if vr and vr.flags else "none"

    prompt = _RISK_SCORE_PROMPT.format(
        vendor=inv.vendor_name if inv else "unknown",
        total=f"{inv.total:,.2f}" if inv and inv.total is not None else "unknown",
        currency=inv.currency if inv else "USD",
        due_date=inv.due_date if inv else "not specified",
        flags=flag_strs,
        notes=inv.notes if inv else "none",
    )

    llm = get_llm()
    resp = invoke_with_retry(llm, prompt)
    raw = (resp.content if hasattr(resp, "content") else str(resp)).strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw.strip())

    try:
        data = json.loads(raw)
        return {
            "risk_score": float(data.get("risk_score", 0.5)),
            "recommendation": str(data.get("recommendation", "REJECT")).upper(),
            "explanation": str(data.get("explanation", "No explanation provided.")),
        }
    except (json.JSONDecodeError, ValueError):
        logger.warning("LLM risk scorer returned non-JSON: %s", raw)
        return {
            "risk_score": 0.5,
            "recommendation": "REJECT",
            "explanation": raw[:300],
        }


# ---------------------------------------------------------------------------
# Main approval node
# ---------------------------------------------------------------------------

def approve(state: InvoiceState) -> dict[str, Any]:
    """LangGraph node: run tiered approval and return partial state update."""
    audit_log: list[str] = list(state.get("audit_log", []))
    fraud_count = _count_fraud_indicators(state)
    warning_cats = _warning_categories(state)
    flag_pattern = _warning_flag_pattern(state)

    # ------------------------------------------------------------------
    # Tier 1 — Fraud auto-reject (2+ indicators)
    # ------------------------------------------------------------------
    if fraud_count >= 2:
        audit_log.append(f"Approval: Tier 1 auto-reject — {fraud_count} fraud indicators")
        result = ApprovalResult(
            decision="REJECTED",
            prosecution_argument=f"Auto-rejected: {fraud_count} fraud indicators detected.",
            defense_argument="N/A",
            final_reasoning=f"Automatic rejection: {fraud_count} fraud risk indicators exceed threshold.",
            risk_score=1.0,
            auto_rejected=True,
            rules_applied=["fraud_indicator_threshold"],
            decision_source="auto_reject",
        )
        return {"approval_result": result, "audit_log": audit_log}

    # ------------------------------------------------------------------
    # Tier 2 — Deterministic rules (no LLM)
    # ------------------------------------------------------------------
    if "currency_mismatch" in warning_cats:
        audit_log.append("Approval: Tier 2 reject — currency_mismatch")
        result = ApprovalResult(
            decision="REJECTED",
            prosecution_argument="Invoice uses non-USD currency, violating payment policy.",
            defense_argument="N/A",
            final_reasoning="Rejected: currency mismatch requires vendor to re-invoice in USD.",
            risk_score=0.7,
            auto_rejected=True,
            rules_applied=["currency_mismatch"],
            decision_source="deterministic",
        )
        return {"approval_result": result, "audit_log": audit_log}

    if not warning_cats and fraud_count == 0:
        audit_log.append("Approval: Tier 2 approve — clean invoice")
        result = ApprovalResult(
            decision="APPROVED",
            prosecution_argument="N/A",
            defense_argument="No flags, no fraud indicators.",
            final_reasoning="Automatically approved: invoice passed all checks with no warnings.",
            risk_score=0.0,
            auto_rejected=False,
            rules_applied=["clean_invoice"],
            decision_source="deterministic",
        )
        return {"approval_result": result, "audit_log": audit_log}

    _minor_warnings = {"arithmetic_mismatch", "duplicate_invoice"}
    if warning_cats.issubset(_minor_warnings) and fraud_count <= 1:
        audit_log.append("Approval: Tier 2 approve — minor warnings only")
        result = ApprovalResult(
            decision="APPROVED",
            prosecution_argument="Minor flags noted.",
            defense_argument="Only minor warnings; no hard fails or currency issues.",
            final_reasoning="Approved: minor warnings do not warrant rejection.",
            risk_score=0.2,
            auto_rejected=False,
            rules_applied=["minor_warnings_only"],
            decision_source="deterministic",
        )
        return {"approval_result": result, "audit_log": audit_log}

    # ------------------------------------------------------------------
    # Tier 2.5 — Precedent self-correction (≥3 consistent decisions)
    # ------------------------------------------------------------------
    precedent = precedent_db.get_precedent(flag_pattern)

    if precedent is not None and precedent["count"] >= 3:
        audit_log.append(
            f"Approval: Tier 2.5 learned_precedent — {precedent['decision']} "
            f"(pattern='{flag_pattern}', count={precedent['count']})"
        )
        result = ApprovalResult(
            decision=precedent["decision"],
            prosecution_argument="N/A (learned precedent)",
            defense_argument="N/A (learned precedent)",
            final_reasoning=precedent["reasoning"],
            risk_score=0.3 if precedent["decision"] == "APPROVED" else 0.7,
            auto_rejected=False,
            rules_applied=["learned_precedent"],
            decision_source="learned_precedent",
        )
        return {"approval_result": result, "audit_log": audit_log}

    # ------------------------------------------------------------------
    # Tier 3 — Single LLM risk scoring → route to human review
    # ------------------------------------------------------------------
    audit_log.append(f"Approval: Tier 3 LLM risk scoring — novel pattern '{flag_pattern}'")

    try:
        scored = _llm_risk_score(state)
    except Exception as exc:
        logger.error("LLM risk scoring failed: %s", exc)
        scored = {
            "risk_score": 0.5,
            "recommendation": "REJECT",
            "explanation": f"LLM unavailable ({exc}). Manual review required.",
        }
        audit_log.append(f"Approval: LLM failed — queuing for review anyway")

    audit_log.append(
        f"Approval: risk_score={scored['risk_score']:.2f}, "
        f"recommendation={scored['recommendation']} — queuing for human review"
    )

    result = ApprovalResult(
        decision="PENDING_REVIEW",
        prosecution_argument="N/A (routed to human review)",
        defense_argument="N/A (routed to human review)",
        final_reasoning=scored["explanation"],
        risk_score=scored["risk_score"],
        auto_rejected=False,
        rules_applied=["llm_risk_score", "human_review_required"],
        decision_source="pending_human",
    )
    # Attach LLM recommendation so the queue node can surface it to the reviewer
    result.llm_recommendation = scored["recommendation"]  # type: ignore[attr-defined]

    return {"approval_result": result, "audit_log": audit_log}
