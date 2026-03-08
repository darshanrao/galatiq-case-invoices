"""Tests for ingestion parsers (JSON, CSV, XML)."""

from pathlib import Path

import pytest

from src.ingestion.parsers import parse_csv, parse_json, parse_xml

INVOICES_DIR = Path(__file__).parent.parent.parent / "data" / "invoices"


def _read(filename: str) -> str:
    return (INVOICES_DIR / filename).read_text(encoding="utf-8")


class TestParseJsonClean:
    """invoice_1004.json — clean JSON with nested vendor."""

    def setup_method(self) -> None:
        self.result = parse_json(_read("invoice_1004.json"))

    def test_invoice_number(self) -> None:
        assert self.result.invoice.invoice_number == "INV-1004"

    def test_vendor_extracted_from_nested_object(self) -> None:
        assert self.result.invoice.vendor_name == "Precision Parts Ltd."

    def test_date(self) -> None:
        assert self.result.invoice.invoice_date == "2026-01-22"

    def test_due_date(self) -> None:
        assert self.result.invoice.due_date == "2026-02-22"

    def test_line_item_count(self) -> None:
        assert len(self.result.line_items) == 2

    def test_first_line_item(self) -> None:
        item = self.result.line_items[0]
        assert item.item == "WidgetA"
        assert item.quantity == 3
        assert item.unit_price == 250.0

    def test_second_line_item(self) -> None:
        item = self.result.line_items[1]
        assert item.item == "WidgetB"
        assert item.quantity == 2
        assert item.unit_price == 500.0

    def test_subtotal(self) -> None:
        assert self.result.invoice.subtotal == 1750.0

    def test_tax_rate(self) -> None:
        assert self.result.invoice.tax_rate == pytest.approx(0.08)

    def test_total(self) -> None:
        assert self.result.invoice.total == pytest.approx(1890.0)

    def test_currency(self) -> None:
        assert self.result.invoice.currency == "USD"


class TestParseJsonNulls:
    """invoice_1009.json — empty vendor, null due_date, negative quantity."""

    def setup_method(self) -> None:
        self.result = parse_json(_read("invoice_1009.json"))

    def test_empty_vendor(self) -> None:
        assert self.result.invoice.vendor_name == ""

    def test_null_due_date(self) -> None:
        assert self.result.invoice.due_date is None

    def test_negative_quantity(self) -> None:
        assert self.result.line_items[0].quantity == -5


class TestParseCsv:
    """CSV parser — key-value and tabular formats."""

    def test_keyvalue_csv_invoice_1006(self) -> None:
        result = parse_csv(_read("invoice_1006.csv"))
        assert result.invoice.invoice_number
        assert len(result.line_items) >= 1

    def test_tabular_csv_invoice_1015(self) -> None:
        result = parse_csv(_read("invoice_1015.csv"))
        assert result.invoice.invoice_number
        assert len(result.line_items) >= 1


class TestParseXml:
    """XML parser — invoice_1014.xml."""

    def test_xml_invoice_1014(self) -> None:
        result = parse_xml(_read("invoice_1014.xml"))
        assert result.invoice.invoice_number
        assert result.invoice.currency == "EUR"
        assert len(result.line_items) >= 1
