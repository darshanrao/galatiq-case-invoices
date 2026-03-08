"""Tests for payment/reject nodes."""

from src.core.models import ApprovalResult, ValidationResult
from src.pipeline.payment import pay, reject

from tests.conftest import sample_bundle


def test_reject_ingestion() -> None:
    state = {
        "invoice": None,
        "ingestion_issues": ["Could not parse file"],
        "validation_result": None,
        "approval_result": None,
    }
    result = reject(state)
    assert result["status"] == "rejected"
    assert result["payment_result"].rejection_stage == "ingestion"


def test_reject_validation() -> None:
    bundle = sample_bundle()
    vr = ValidationResult(passed=False, flags=[])
    state = {
        "invoice": bundle,
        "ingestion_issues": [],
        "validation_result": vr,
        "approval_result": None,
    }
    result = reject(state)
    assert result["status"] == "rejected"
    assert result["payment_result"].rejection_stage == "validation"


def test_reject_approval() -> None:
    bundle = sample_bundle()
    ar = ApprovalResult(
        decision="REJECTED",
        prosecution_argument="",
        defense_argument="",
        final_reasoning="Risky vendor",
        risk_score=0.8,
        auto_rejected=True,
        rules_applied=[],
        decision_source="auto_reject",
    )
    vr = ValidationResult(passed=True, flags=[])
    state = {
        "invoice": bundle,
        "ingestion_issues": [],
        "validation_result": vr,
        "approval_result": ar,
    }
    result = reject(state)
    assert result["status"] == "rejected"
    assert result["payment_result"].rejection_stage == "approval"


def test_pay_success() -> None:
    bundle = sample_bundle()
    state = {
        "invoice": bundle,
        "audit_log": [],
    }
    result = pay(state)
    assert result["status"] == "paid"
    assert result["payment_result"].status == "paid"
    assert result["payment_result"].transaction_id
