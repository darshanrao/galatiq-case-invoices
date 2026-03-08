"""Tests for human review queue."""

import pytest

from src.persistence import review_queue


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "review_queue.db"
    review_queue.init_review_queue(db_path)
    return db_path


def test_enqueue_returns_review_id(db) -> None:
    rid = review_queue.enqueue(
        file_path="/tmp/inv.txt",
        invoice_number="INV-1001",
        vendor="Acme",
        amount=1000.0,
        flag_pattern="arithmetic_mismatch",
        risk_score=0.3,
        recommendation="APPROVE",
        flag_explanation="Minor discrepancy.",
        db_path=db,
    )
    assert rid
    assert len(rid) == 36  # UUID format


def test_get_review(db) -> None:
    rid = review_queue.enqueue(
        file_path="/tmp/inv.txt",
        invoice_number="INV-1001",
        vendor="Acme",
        amount=1000.0,
        flag_pattern="x",
        risk_score=0.3,
        recommendation="APPROVE",
        flag_explanation="OK",
        db_path=db,
    )
    r = review_queue.get_review(rid, db_path=db)
    assert r is not None
    assert r["invoice_number"] == "INV-1001"
    assert r["status"] == "pending"


def test_list_reviews(db) -> None:
    review_queue.enqueue(
        "/tmp/a.txt", "INV-1", "V1", 100.0, "x", 0.5, "APPROVE", "ok", db_path=db
    )
    items = review_queue.list_reviews(db_path=db)
    assert len(items) >= 1


def test_decide_updates_status(db) -> None:
    rid = review_queue.enqueue(
        "/tmp/inv.txt", "INV-1", "V1", 100.0, "x", 0.5, "APPROVE", "ok", db_path=db
    )
    result = review_queue.decide(
        rid,
        "APPROVED",
        "Looks good.",
        db_path=db,
        precedent_db_path=db.parent / "precedent.db",
    )
    assert result["status"] == "approved"
