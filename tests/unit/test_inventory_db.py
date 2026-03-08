"""Tests for inventory database (lookup, fuzzy match, duplicate tracking)."""

import pytest

from src.persistence import inventory_db

# Uses inventory_db.init_inventory_db which seeds WidgetA(15), WidgetB(10), GadgetX(5), GadgetZ(0)
# FRAUD_ITEMS = {FakeItem}


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "inventory.db"
    inventory_db.init_inventory_db(db_path)
    return db_path


def test_init_seeds_inventory(db) -> None:
    r = inventory_db.get_item("WidgetA", db_path=db)
    assert r is not None
    assert r["stock"] == 15


def test_get_item_exact(db) -> None:
    r = inventory_db.get_item("WidgetA", db_path=db)
    assert r is not None
    assert r["item"] == "WidgetA"
    assert r["stock"] == 15


def test_get_item_not_found(db) -> None:
    r = inventory_db.get_item("SuperGizmo", db_path=db)
    assert r is None


def test_is_fraud_item() -> None:
    assert inventory_db.is_fraud_item("FakeItem") is True
    assert inventory_db.is_fraud_item("WidgetA") is False


def test_fuzzy_match_widget_a_with_space(db) -> None:
    r = inventory_db.fuzzy_match_item("Widget A", db_path=db)
    assert r["found"] is True
    assert r["best_match"] == "WidgetA"


def test_fuzzy_match_gadget_x(db) -> None:
    r = inventory_db.fuzzy_match_item("Gadget X", db_path=db)
    assert r["found"] is True
    assert r["best_match"] == "GadgetX"


def test_fuzzy_super_gizmo_not_found(db) -> None:
    r = inventory_db.fuzzy_match_item("SuperGizmo", db_path=db)
    assert r["found"] is False


def test_fuzzy_widget_c_not_found(db) -> None:
    """WidgetC should not match WidgetA at 0.9 threshold."""
    r = inventory_db.fuzzy_match_item("WidgetC", db_path=db)
    assert r["found"] is False


def test_is_duplicate_mark_processed(db) -> None:
    assert inventory_db.is_duplicate("INV-1001", db_path=db) is False
    inventory_db.mark_processed("INV-1001", db_path=db)
    assert inventory_db.is_duplicate("INV-1001", db_path=db) is True
