"""Pipeline runner: executes the LangGraph invoice processing pipeline."""

from __future__ import annotations

from typing import Callable, Optional

from src.core.models import InvoiceState
from src.persistence import inventory_db
from src.pipeline import graph as graph_module


def run(
    file_path: str,
    db_path: str | None = None,
    on_stage_complete: Optional[Callable[[str, dict], None]] = None,
) -> InvoiceState:
    """Run a single invoice through the full pipeline.

    Args:
        file_path:          Path to the invoice file.
        db_path:            Optional path to inventory.db.
        on_stage_complete:  Optional callback called after each stage completes.
                            Signature: callback(stage_name: str, partial_state: dict)
    """
    graph_module._on_stage_complete = on_stage_complete

    inventory_db.init_inventory_db(db_path)
    initial_state: InvoiceState = {
        "file_path": str(file_path),
        "db_path": db_path,
        "status": "pending",
        "audit_log": [],
        "ingestion_attempts": 0,
    }
    try:
        return _get_graph().invoke(initial_state)
    finally:
        graph_module._on_stage_complete = None


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from src.pipeline.graph import build_graph
        _graph = build_graph()
    return _graph
