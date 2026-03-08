"""Tests for fraud indicator detection in approval stage."""

from tests.conftest import sample_bundle

from src.approval.fraud_detection import count_fraud_indicators


def test_zero_indicators_clean_invoice() -> None:
    bundle = sample_bundle()
    state = {"invoice": bundle}
    assert count_fraud_indicators(state) == 0


def test_suspicious_vendor_keyword() -> None:
    bundle = sample_bundle(vendor_name="Urgent Supplies Inc.")
    state = {"invoice": bundle}
    assert count_fraud_indicators(state) >= 1


def test_urgency_phrase_in_notes() -> None:
    bundle = sample_bundle(notes="Please pay immediately to avoid penalties")
    state = {"invoice": bundle}
    assert count_fraud_indicators(state) >= 1


def test_none_due_date() -> None:
    bundle = sample_bundle(due_date=None)
    state = {"invoice": bundle}
    assert count_fraud_indicators(state) >= 1


def test_high_total() -> None:
    bundle = sample_bundle(total=60_000.0)
    state = {"invoice": bundle}
    assert count_fraud_indicators(state) >= 1


def test_inv_1003_style_fraudster() -> None:
    """Fraudster LLC, URGENT notes, >$50K, None due_date = 2+ indicators."""
    bundle = sample_bundle(
        vendor_name="Fraudster LLC",
        total=100_000.0,
        due_date=None,
        notes="URGENT - wire transfer required",
    )
    state = {"invoice": bundle}
    assert count_fraud_indicators(state) >= 2


def test_empty_bundle_returns_zero() -> None:
    state = {"invoice": None}
    assert count_fraud_indicators(state) == 0
