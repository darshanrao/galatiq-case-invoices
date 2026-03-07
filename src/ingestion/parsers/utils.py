"""Shared parsing utilities for invoice parsers."""

import re


def _parse_currency(val: str | float | None) -> float | None:
    """Parse a currency string like '$5,000.00' or number to float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "")
    m = re.search(r"[\d.-]+", s)
    return float(m.group()) if m else None


def _parse_int(val: str | int | None) -> int | None:
    """Parse quantity to int."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    m = re.search(r"-?\d+", str(val))
    return int(m.group()) if m else None
