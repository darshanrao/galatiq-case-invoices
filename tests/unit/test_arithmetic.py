"""Tests for arithmetic verification (line items vs claimed total)."""

from src.core.models import LineItem
from src.validation.arithmetic import verify_arithmetic


def test_exact_match() -> None:
    line_items = [
        LineItem(item="WidgetA", quantity=10, unit_price=250.0),
        LineItem(item="WidgetB", quantity=5, unit_price=500.0),
    ]
    claimed_total = 5000.0
    result = verify_arithmetic(line_items, claimed_subtotal=5000.0, claimed_total=claimed_total)
    assert result.matches is True
    assert abs(result.discrepancy) < 0.01


def test_small_discrepancy_tolerated() -> None:
    line_items = [
        LineItem(item="WidgetA", quantity=10, unit_price=250.0),
    ]
    result = verify_arithmetic(
        line_items,
        claimed_subtotal=2500.0,
        claimed_total=2500.001,  # within $0.01 tolerance
    )
    assert result.matches is True


def test_large_discrepancy() -> None:
    line_items = [
        LineItem(item="WidgetA", quantity=10, unit_price=250.0),
    ]
    result = verify_arithmetic(
        line_items,
        claimed_subtotal=2500.0,
        claimed_total=2550.0,  # $50 over
    )
    assert result.matches is False
    assert abs(result.discrepancy - 50.0) < 0.01


def test_tax_included() -> None:
    line_items = [
        LineItem(item="WidgetA", quantity=10, unit_price=250.0),
    ]
    result = verify_arithmetic(
        line_items,
        claimed_subtotal=2500.0,
        claimed_total=2700.0,
        tax_rate=0.08,
    )
    # 2500 * 1.08 = 2700
    assert result.matches is True


def test_none_claimed_total_skips_check() -> None:
    line_items = [
        LineItem(item="WidgetA", quantity=10, unit_price=250.0),
    ]
    result = verify_arithmetic(
        line_items,
        claimed_subtotal=2500.0,
        claimed_total=None,
    )
    assert result.matches is True
    assert result.computed_total == 2500.0
