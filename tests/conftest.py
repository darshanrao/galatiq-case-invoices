"""Shared pytest fixtures for galatiq-case-invoices tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.core.models import (
    ApprovalResult,
    Flag,
    Invoice,
    InvoiceBundle,
    LineItem,
    Severity,
    ValidationResult,
)
from src.persistence import inventory_db, precedent_db, review_queue

DATA_DIR = Path(__file__).parent.parent / "data" / "invoices"


@pytest.fixture
def fresh_inventory_db(tmp_path: Path):
    """Provide an isolated inventory.db for each test."""
    db_path = tmp_path / "inventory.db"
    inventory_db.init_inventory_db(db_path)
    return db_path


@pytest.fixture
def fresh_precedent_db(tmp_path: Path):
    """Provide an isolated precedent.db for each test."""
    db_path = tmp_path / "precedent.db"
    precedent_db.init_precedent_db(db_path)
    return db_path


@pytest.fixture
def isolated_dbs(tmp_path: Path):
    """Provide isolated DBs for integration tests (inventory, precedent, review_queue)."""
    inv_path = tmp_path / "inventory.db"
    prec_path = tmp_path / "precedent.db"
    rq_path = tmp_path / "review_queue.db"

    inventory_db.init_inventory_db(inv_path)
    precedent_db.init_precedent_db(prec_path)
    review_queue.init_review_queue(rq_path)

    return {
        "inventory": inv_path,
        "precedent": prec_path,
        "review_queue": rq_path,
    }


def sample_bundle(
    invoice_number: str = "INV-1001",
    vendor_name: str = "Widgets Inc.",
    total: float = 5000.0,
    currency: str = "USD",
    due_date: str | None = "2026-02-01",
    notes: str | None = None,
) -> InvoiceBundle:
    """Build a minimal InvoiceBundle for testing."""
    inv = Invoice(
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_date="2026-01-15",
        due_date=due_date,
        currency=currency,
        total=total,
        payment_terms="Net 15",
        notes=notes,
    )
    line_items = [
        LineItem(item="WidgetA", quantity=10, unit_price=250.0, line_total=2500.0),
        LineItem(item="WidgetB", quantity=5, unit_price=500.0, line_total=2500.0),
    ]
    return InvoiceBundle(invoice=inv, line_items=line_items)


def sample_validation_passed(flags: list[Flag] | None = None) -> ValidationResult:
    """Build a ValidationResult that passed (no HARD_FAIL)."""
    return ValidationResult(
        passed=True,
        flags=flags or [],
    )


def sample_validation_failed(flags: list[Flag]) -> ValidationResult:
    """Build a ValidationResult that failed (has HARD_FAIL)."""
    return ValidationResult(
        passed=False,
        flags=flags,
    )


def mock_llm_json_response(content: str) -> MagicMock:
    """Build a mock LLM response with .content attribute."""
    resp = MagicMock()
    resp.content = content
    return resp
