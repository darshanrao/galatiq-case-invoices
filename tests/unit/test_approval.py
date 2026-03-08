"""Tests for approval service (tiered: fraud, deterministic, precedent, LLM)."""

from unittest.mock import MagicMock, patch

from src.core.models import ApprovalResult, Flag, Severity, ValidationResult
from src.approval.service import approve

from tests.conftest import sample_bundle, sample_validation_passed


def _state(bundle, validation_result, **kwargs):
    return {
        "invoice": bundle,
        "validation_result": validation_result,
        "audit_log": [],
        **kwargs,
    }


def test_fraud_auto_reject_two_indicators() -> None:
    bundle = sample_bundle(
        vendor_name="Urgent Supplies Inc.",
        total=60_000.0,
        due_date=None,
        notes="pay immediately",
    )
    vr = sample_validation_passed()
    state = _state(bundle, vr)
    result = approve(state)
    ar = result["approval_result"]
    assert ar.decision == "REJECTED"
    assert ar.auto_rejected is True


def test_clean_invoice_deterministic_approve() -> None:
    bundle = sample_bundle()
    vr = sample_validation_passed()
    state = _state(bundle, vr)
    result = approve(state)
    ar = result["approval_result"]
    assert ar.decision == "APPROVED"
    assert ar.decision_source == "deterministic"


def test_precedent_auto_decide(fresh_precedent_db) -> None:
    from src.persistence import precedent_db

    precedent_db.store_decision(
        "arithmetic_mismatch",
        "APPROVED",
        "Minor, approved.",
        db_path=fresh_precedent_db,
    )
    precedent_db.store_decision(
        "arithmetic_mismatch",
        "APPROVED",
        "OK",
        db_path=fresh_precedent_db,
    )
    precedent_db.store_decision(
        "arithmetic_mismatch",
        "APPROVED",
        "OK",
        db_path=fresh_precedent_db,
    )

    bundle = sample_bundle()
    vr = ValidationResult(
        passed=True,
        flags=[
            Flag(Severity.WARNING, "arithmetic_mismatch", "Math off", None, None),
        ],
    )
    state = _state(bundle, vr)

    with patch("src.approval.service.precedent_db") as mock_pdb:
        mock_pdb.get_precedent.return_value = {
            "decision": "APPROVED",
            "reasoning": "Learned from history",
            "count": 3,
            "source": "llm",
        }
        result = approve(state)

    ar = result["approval_result"]
    assert ar.decision == "APPROVED"
    assert ar.decision_source == "learned_precedent"


def test_novel_pattern_queues_for_review() -> None:
    bundle = sample_bundle()
    vr = ValidationResult(
        passed=True,
        flags=[
            Flag(Severity.WARNING, "arithmetic_mismatch", "Math off", None, None),
        ],
    )
    state = _state(bundle, vr)

    mock_llm = MagicMock()
    resp = MagicMock()
    resp.content = '{"risk_score": 0.4, "recommendation": "APPROVE", "explanation": "Minor issue."}'
    mock_llm.invoke.return_value = resp

    with patch("src.approval.service.get_llm", return_value=mock_llm), \
         patch("src.approval.service.invoke_with_retry", side_effect=lambda llm, prompt: resp):
        result = approve(state)

    ar = result["approval_result"]
    assert ar.decision == "PENDING_REVIEW"
