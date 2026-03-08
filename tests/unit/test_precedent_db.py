"""Tests for precedent database (approval learning)."""

import pytest

from src.persistence import precedent_db


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "precedent.db"
    precedent_db.init_precedent_db(db_path)
    return db_path


def test_get_precedent_empty(db) -> None:
    assert precedent_db.get_precedent("arithmetic_mismatch", db_path=db) is None


def test_store_and_get_precedent(db) -> None:
    precedent_db.store_decision(
        "arithmetic_mismatch",
        "APPROVED",
        "Minor discrepancy, approved.",
        source="llm",
        db_path=db,
    )
    p = precedent_db.get_precedent("arithmetic_mismatch", db_path=db)
    assert p is not None
    assert p["decision"] == "APPROVED"
    assert p["count"] == 1


def test_same_decision_increments_count(db) -> None:
    precedent_db.store_decision("x", "APPROVED", "r1", db_path=db)
    precedent_db.store_decision("x", "APPROVED", "r2", db_path=db)
    precedent_db.store_decision("x", "APPROVED", "r3", db_path=db)
    p = precedent_db.get_precedent("x", db_path=db)
    assert p["count"] == 3


def test_record_human_override_sets_count_three(db) -> None:
    precedent_db.record_human_override(
        "currency_mismatch",
        "REJECTED",
        "Non-USD not allowed.",
        db_path=db,
    )
    p = precedent_db.get_precedent("currency_mismatch", db_path=db)
    assert p is not None
    assert p["decision"] == "REJECTED"
    assert p["count"] == 3
    assert p["source"] == "human"
