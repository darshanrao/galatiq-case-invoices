"""Core data models for the invoice processing pipeline."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LineItem:
    """A single line item on an invoice."""

    item: str
    quantity: int
    unit_price: float
    line_total: Optional[float] = None
    note: Optional[str] = None


@dataclass
class Invoice:
    """Invoice header and metadata."""

    invoice_number: str
    vendor_name: str
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    vendor_address: Optional[str] = None
    revision: Optional[str] = None
    currency: str = "USD"
    payment_terms: Optional[str] = None
    subtotal: Optional[float] = None
    tax_rate: Optional[float] = None
    tax_amount: Optional[float] = None
    total: Optional[float] = None
    shipping: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class InvoiceBundle:
    """Normalized invoice with its line items."""

    invoice: Invoice
    line_items: list[LineItem] = field(default_factory=list)


@dataclass
class LineItemValidationResult:
    """Validation result for a single line item."""

    item: str
    quantity: int
    status: str  # valid, invalid_quantity, fake_item, unknown_item, out_of_stock, stock_mismatch
    message: str = ""


@dataclass
class ValidationResult:
    """Overall validation result for an invoice."""

    invoice_number: str
    overall_status: str  # valid, suspicious, invalid
    line_item_results: list[LineItemValidationResult] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
