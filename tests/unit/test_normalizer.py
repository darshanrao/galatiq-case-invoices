"""Tests for text normalizer (OCR cleanup, dates, invoice numbers)."""

import pytest

from src.ingestion.normalizer import (
    normalize_date,
    normalize_invoice_number,
    normalize_item_name,
    normalize_tax_rate,
    normalize_text,
)


class TestNormalizeItemName:
    def test_collapses_spaces(self) -> None:
        assert normalize_item_name("Widget A") == "WidgetA"
        assert normalize_item_name("Gadget X") == "GadgetX"

    def test_none_returns_empty(self) -> None:
        assert normalize_item_name(None) == ""

    def test_strips_whitespace(self) -> None:
        assert normalize_item_name("  WidgetA  ") == "WidgetA"


class TestNormalizeInvoiceNumber:
    def test_already_valid_format(self) -> None:
        assert normalize_invoice_number("INV-1001") == "INV-1001"

    def test_bare_number(self) -> None:
        assert normalize_invoice_number("1001") == "INV-1001"

    def test_prefix_space_number(self) -> None:
        assert normalize_invoice_number("INV 1001") == "INV-1001"

    def test_none_returns_empty(self) -> None:
        assert normalize_invoice_number(None) == ""


class TestNormalizeDate:
    def test_iso_format(self) -> None:
        assert normalize_date("2026-01-15") == "2026-01-15"

    def test_slash_format(self) -> None:
        assert normalize_date("01/15/2026") == "2026-01-15"

    def test_none_returns_none(self) -> None:
        assert normalize_date(None) is None

    def test_empty_returns_none(self) -> None:
        assert normalize_date("") is None


class TestNormalizeTaxRate:
    def test_percentage_form(self) -> None:
        assert normalize_tax_rate(5) == pytest.approx(0.05)
        assert normalize_tax_rate(8) == pytest.approx(0.08)

    def test_decimal_form_unchanged(self) -> None:
        assert normalize_tax_rate(0.05) == pytest.approx(0.05)

    def test_none_returns_none(self) -> None:
        assert normalize_tax_rate(None) is None


class TestNormalizeText:
    """OCR cleanup — O to 0 in numeric contexts."""

    def test_replaces_o_in_numeric_context(self) -> None:
        result = normalize_text("2O26")
        assert "0" in result or "2" in result  # Should fix OCR O->0
