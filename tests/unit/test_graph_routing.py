"""Tests for LangGraph routing functions."""

from src.pipeline.graph import (
    route_after_approval,
    route_after_ingestion,
    route_after_validation,
)


def test_ingestion_success_routes_validate() -> None:
    state = {"invoice": object(), "ingestion_attempts": 1}
    assert route_after_ingestion(state) == "validate"


def test_ingestion_retry() -> None:
    state = {"invoice": None, "ingestion_attempts": 1, "ingestion_issues": ["missing field"]}
    assert route_after_ingestion(state) == "ingest"


def test_ingestion_max_retries_reject() -> None:
    state = {"invoice": None, "ingestion_attempts": 2, "ingestion_issues": ["still failing"]}
    assert route_after_ingestion(state) == "reject"


def test_validation_passed_routes_approve() -> None:
    vr = type("VR", (), {"passed": True})()
    state = {"validation_result": vr}
    assert route_after_validation(state) == "approve"


def test_validation_failed_routes_reject() -> None:
    vr = type("VR", (), {"passed": False})()
    state = {"validation_result": vr}
    assert route_after_validation(state) == "reject"


def test_validation_none_routes_reject() -> None:
    state = {"validation_result": None}
    assert route_after_validation(state) == "reject"


def test_approval_approved_routes_approved_node() -> None:
    ar = type("AR", (), {"decision": "APPROVED"})()
    state = {"approval_result": ar}
    assert route_after_approval(state) == "approved"


def test_approval_rejected_routes_reject() -> None:
    ar = type("AR", (), {"decision": "REJECTED"})()
    state = {"approval_result": ar}
    assert route_after_approval(state) == "reject"


def test_approval_pending_routes_queue_for_review() -> None:
    ar = type("AR", (), {"decision": "PENDING_REVIEW"})()
    state = {"approval_result": ar}
    assert route_after_approval(state) == "queue_for_review"


def test_approval_none_routes_reject() -> None:
    state = {"approval_result": None}
    assert route_after_approval(state) == "reject"
