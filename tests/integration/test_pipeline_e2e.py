"""End-to-end pipeline tests with mocked LLM."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.persistence import inventory_db, precedent_db, review_queue
from src.pipeline.runner import run

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "invoices"

# Expected: (filename, expected_status, expected_rejection_stage or None)
DETERMINISTIC = [
    ("invoice_1001.txt", "approved", None),   # needs LLM parse
    ("invoice_1004.json", "approved", None),
    ("invoice_1004_revised.json", "approved", None),
    ("invoice_1005.json", "rejected", "validation"),
    ("invoice_1006.csv", "approved", None),
    ("invoice_1007.csv", "rejected", "validation"),
    ("invoice_1009.json", "rejected", "validation"),
    ("invoice_1014.xml", "rejected", "approval"),
    ("invoice_1015.csv", "approved", None),
    ("invoice_1016.json", "rejected", "validation"),
]

LLM_INVOICES = [
    ("invoice_1002.txt", "rejected", "validation"),
    ("invoice_1003.txt", "rejected", "approval"),
    ("invoice_1008.txt", "rejected", "validation"),
    ("invoice_1010.txt", "approved", None),
]


def _mock_llm_for_approval():
    mock = MagicMock()
    resp = MagicMock()
    resp.content = '{"risk_score": 0.2, "recommendation": "APPROVE", "explanation": "OK"}'
    mock.invoke.return_value = resp
    return mock


def _mock_llm_for_text_parse(filename: str):
    """Return mock LLM responses for text invoice parsing + approval."""
    responses = {
        "invoice_1001.txt": '{"invoice_number": "INV-1001", "vendor_name": "Widgets Inc.", "invoice_date": "2026-01-15", "due_date": "2026-02-01", "line_items": [{"item": "WidgetA", "quantity": 10, "unit_price": 250}, {"item": "WidgetB", "quantity": 5, "unit_price": 500}], "total": 5000, "currency": "USD", "payment_terms": "Net 15"}',
        "invoice_1002.txt": '{"invoice_number": "INV-1002", "vendor_name": "Gadgets Co.", "invoice_date": "2026-01-30", "due_date": "2026-01-30", "line_items": [{"item": "GadgetX", "quantity": 20, "unit_price": 750}], "total": 15000, "currency": "USD"}',
        "invoice_1003.txt": '{"invoice_number": "INV-1003", "vendor_name": "Fraudster LLC", "invoice_date": "2026-01-20", "due_date": null, "line_items": [{"item": "FakeItem", "quantity": 100, "unit_price": 1000}], "total": 100000, "currency": "USD"}',
        "invoice_1008.txt": '{"invoice_number": "INV-1008", "vendor_name": "NoProd", "invoice_date": "2026-01-10", "due_date": "2026-01-20", "line_items": [{"item": "SuperGizmo", "quantity": 12, "unit_price": 400}, {"item": "MegaSprocket", "quantity": 6, "unit_price": 850}], "total": 9900, "currency": "USD"}',
        "invoice_1010.txt": '{"invoice_number": "INV-1010", "vendor_name": "Consolidated", "invoice_date": "2026-01-27", "due_date": "2026-02-26", "line_items": [{"item": "WidgetA", "quantity": 8, "unit_price": 250}, {"item": "WidgetA", "quantity": 4, "unit_price": 300}, {"item": "WidgetB", "quantity": 4, "unit_price": 500}, {"item": "GadgetX", "quantity": 2, "unit_price": 750}], "total": 7185, "currency": "USD"}',
    }
    content = responses.get(filename, '{}')
    mock = MagicMock()
    resp = MagicMock()
    resp.content = content
    mock.invoke.return_value = resp
    return mock


@pytest.fixture
def isolated_dbs(tmp_path):
    inv_path = tmp_path / "inventory.db"
    prec_path = tmp_path / "precedent.db"
    rq_path = tmp_path / "review_queue.db"
    inventory_db.init_inventory_db(inv_path)
    precedent_db.init_precedent_db(prec_path)
    review_queue.init_review_queue(rq_path)
    return {"inventory": inv_path, "precedent": prec_path, "review_queue": rq_path}


def _run_with_dbs(file_path: str, db_path: Path) -> dict:
    return run(file_path, db_path=str(db_path))


@pytest.mark.parametrize("filename,expected_status,expected_stage", [
    ("invoice_1004.json", "approved", None),
    ("invoice_1005.json", "rejected", "validation"),
    ("invoice_1006.csv", "approved", None),
    ("invoice_1007.csv", "rejected", "validation"),
    ("invoice_1009.json", "rejected", "validation"),
    ("invoice_1014.xml", "pending_review", None),  # EUR → human review
    ("invoice_1015.csv", "approved", None),
    ("invoice_1016.json", "rejected", "validation"),
])
def test_deterministic_invoices(filename, expected_status, expected_stage, isolated_dbs):
    file_path = DATA_DIR / filename
    if not file_path.exists():
        pytest.skip(f"Test file not found: {file_path}")

    mock_llm = _mock_llm_for_approval()
    with patch("src.ingestion.llm_extract.get_llm", return_value=mock_llm), \
         patch("src.approval.service.get_llm", return_value=mock_llm), \
         patch("src.approval.service.invoke_with_retry", side_effect=lambda llm, p: mock_llm.invoke.return_value):
        state = _run_with_dbs(str(file_path), isolated_dbs["inventory"])

    assert state.get("status") == expected_status, (
        f"{filename}: expected {expected_status}, got {state.get('status')}"
    )
    if expected_stage:
        pr = state.get("payment_result")
        assert pr is not None, f"{filename}: missing payment_result"
        assert pr.rejection_stage == expected_stage


def test_inv_1003_rejected(isolated_dbs):
    """INV-1003: Pass validation (valid items) but get fraud auto-reject at approval.
    Patch extract_invoice_with_llm to return a bundle with valid items + fraud signals."""
    from src.core.models import Invoice, InvoiceBundle, LineItem

    fraud_bundle = InvoiceBundle(
        invoice=Invoice(
            invoice_number="INV-1003",
            vendor_name="Urgent Wire Transfer Co.",
            invoice_date="2026-01-20",
            due_date=None,
            total=60_000.0,
            currency="USD",
            notes="pay immediately wire transfer",
        ),
        line_items=[LineItem(item="WidgetA", quantity=2, unit_price=250.0, line_total=500.0)],
    )

    def fake_extract(raw, missing_critical_fields=None):
        return fraud_bundle

    file_path = str(DATA_DIR / "invoice_1003.txt")
    with patch("src.ingestion.llm_extract.extract_invoice_with_llm", side_effect=fake_extract):
        state = _run_with_dbs(file_path, isolated_dbs["inventory"])

    assert state.get("status") == "rejected"
    ar = state.get("approval_result")
    assert ar is not None
    assert ar.auto_rejected is True
