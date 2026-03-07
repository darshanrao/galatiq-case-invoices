"""Core data models for the invoice processing pipeline."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from typing_extensions import TypedDict


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


# ---------------------------------------------------------------------------
# Validation models
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """Severity of a validation flag."""

    HARD_FAIL = "HARD_FAIL"  # blocks approval
    WARNING = "WARNING"      # advisory; invoice can still pass
    INFO = "INFO"            # informational only


class MatchType(str, Enum):
    """How an invoice item was matched to inventory."""

    exact = "exact"
    fuzzy = "fuzzy"
    unknown = "unknown"


@dataclass
class Flag:
    """A single validation finding."""

    severity: Severity
    category: str           # e.g. "stock_exceeded", "arithmetic_mismatch"
    message: str
    field: Optional[str] = None    # which invoice field triggered this
    details: Optional[str] = None  # machine-readable key=value context


@dataclass
class ItemMatch:
    """Result of resolving one invoice item against inventory."""

    item_name: str
    matched_to: Optional[str]
    match_type: MatchType
    similarity_score: Optional[float] = None


@dataclass
class ArithmeticResult:
    """Outcome of the arithmetic verification check."""

    computed_total: float
    claimed_total: float
    matches: bool         # True if abs(discrepancy) < $0.01
    discrepancy: float    # claimed_total - computed_total (positive = overbilling)


@dataclass
class ValidationResult:
    """Full validation outcome for an invoice."""

    passed: bool                                          # False if any HARD_FAIL flag
    flags: list[Flag] = field(default_factory=list)
    item_matches: list[ItemMatch] = field(default_factory=list)
    aggregate_quantities: dict[str, float] = field(default_factory=dict)
    arithmetic_check: Optional[ArithmeticResult] = None


# ---------------------------------------------------------------------------
# Approval & Payment models
# ---------------------------------------------------------------------------


@dataclass
class ApprovalResult:
    """Outcome of the VP-level approval stage."""

    decision: str                    # "APPROVED" | "REJECTED" | "PENDING_REVIEW"
    prosecution_argument: str
    defense_argument: str
    final_reasoning: str
    risk_score: float                # 0.0–1.0
    auto_rejected: bool
    rules_applied: list[str]
    decision_source: str             # "deterministic"|"learned_precedent"|"auto_reject"|"pending_human"
    llm_recommendation: Optional[str] = None  # "APPROVE"|"REJECT" — LLM soft suggestion for reviewer


@dataclass
class ReviewItem:
    """A pending human review entry stored in the review queue."""

    id: str                          # UUID
    file_path: str
    invoice_number: str
    vendor: str
    amount: float
    flag_pattern: str
    risk_score: float
    recommendation: str              # "APPROVE" | "REJECT"
    flag_explanation: str            # Plain-English explanation for reviewer
    status: str                      # "pending" | "approved" | "rejected"
    created_at: str
    decided_at: Optional[str] = None
    decision_reasoning: Optional[str] = None


@dataclass
class PaymentResult:
    """Outcome of the payment execution stage."""

    status: str                      # "paid" | "rejected"
    vendor: str
    amount: float
    rejection_reason: Optional[str] = None
    rejection_stage: Optional[str] = None  # "ingestion"|"validation"|"approval"


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------


class InvoiceState(TypedDict, total=False):
    """Shared state passed between LangGraph nodes."""

    file_path: str
    raw_content: str
    invoice: Optional[Any]           # InvoiceBundle (avoid circular import)
    ingestion_attempts: int
    ingestion_issues: list[str]
    validation_result: Optional[Any]  # ValidationResult
    approval_result: Optional[Any]    # ApprovalResult
    payment_result: Optional[Any]     # PaymentResult
    status: str                       # "pending"|"approved"|"rejected"|"pending_review"|"error"
    audit_log: list[str]
    review_id: Optional[str]          # set when status="pending_review"
