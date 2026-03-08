"""Tests for validation service."""

from functools import partial

from src.core.models import InvoiceBundle, LineItem, Severity
from src.persistence import inventory_db
from src.validation.service import validate_invoice

from tests.conftest import sample_bundle


def test_empty_vendor_hard_fail(fresh_inventory_db) -> None:
    bundle = sample_bundle(vendor_name="")
    get_item = partial(inventory_db.get_item, db_path=fresh_inventory_db)
    result = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    assert result.passed is False
    categories = [f.category for f in result.flags]
    assert "empty_vendor" in categories


def test_negative_quantity_hard_fail(fresh_inventory_db) -> None:
    bundle = sample_bundle()
    bundle.line_items[0].quantity = -5
    get_item = partial(inventory_db.get_item, db_path=fresh_inventory_db)
    result = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    assert result.passed is False
    categories = [f.category for f in result.flags]
    assert "negative_quantity" in categories


def test_fake_item_hard_fail(fresh_inventory_db) -> None:
    bundle = sample_bundle()
    bundle.line_items = [
        LineItem(item="FakeItem", quantity=1, unit_price=100.0),
    ]
    get_item = partial(inventory_db.get_item, db_path=fresh_inventory_db)
    result = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    assert result.passed is False
    categories = [f.category for f in result.flags]
    assert "fake_item" in categories


def test_stock_exceeded(fresh_inventory_db) -> None:
    bundle = sample_bundle()
    bundle.line_items = [
        LineItem(item="GadgetX", quantity=20, unit_price=750.0),
    ]
    get_item = partial(inventory_db.get_item, db_path=fresh_inventory_db)
    result = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    assert result.passed is False
    categories = [f.category for f in result.flags]
    assert "stock_exceeded" in categories


def test_unknown_item(fresh_inventory_db) -> None:
    bundle = sample_bundle()
    bundle.line_items = [
        LineItem(item="SuperGizmo", quantity=5, unit_price=100.0),
    ]
    get_item = partial(inventory_db.get_item, db_path=fresh_inventory_db)
    result = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    assert result.passed is False
    categories = [f.category for f in result.flags]
    assert "unknown_item" in categories


def test_aggregate_quantities(fresh_inventory_db) -> None:
    bundle = sample_bundle()
    bundle.line_items = [
        LineItem(item="WidgetA", quantity=8, unit_price=250.0),
        LineItem(item="WidgetA", quantity=4, unit_price=300.0),
        LineItem(item="WidgetB", quantity=2, unit_price=500.0),
    ]
    get_item = partial(inventory_db.get_item, db_path=fresh_inventory_db)
    result = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    assert result.passed is True
    assert result.aggregate_quantities.get("WidgetA") == 12.0
    assert result.aggregate_quantities.get("WidgetB") == 2.0


def test_currency_mismatch_warning(fresh_inventory_db) -> None:
    bundle = sample_bundle(currency="EUR")
    get_item = partial(inventory_db.get_item, db_path=fresh_inventory_db)
    result = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    categories = [f.category for f in result.flags]
    assert "currency_mismatch" in categories


def test_clean_invoice_passes(fresh_inventory_db) -> None:
    bundle = sample_bundle()
    get_item = partial(inventory_db.get_item, db_path=fresh_inventory_db)
    result = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    assert result.passed is True


def test_duplicate_invoice_warning(fresh_inventory_db) -> None:
    bundle = sample_bundle()
    get_item = partial(inventory_db.get_item, db_path=fresh_inventory_db)
    # First run: passes, marks as processed
    r1 = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    assert r1.passed is True
    # Second run: should flag duplicate (WARNING, not HARD_FAIL)
    r2 = validate_invoice(
        bundle,
        get_item=get_item,
        is_fraud_item=inventory_db.is_fraud_item,
        db_path=fresh_inventory_db,
    )
    categories = [f.category for f in r2.flags]
    assert "duplicate_invoice" in categories
