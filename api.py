"""
FastAPI backend — invoice processing pipeline + dashboard API.

Endpoints:
    POST /api/upload              — upload single invoice, kick off pipeline
    POST /api/upload/batch        — upload multiple invoices
    GET  /api/invoices            — list all invoices (?status= &vendor=)
    GET  /api/invoices/{id}       — full invoice detail with stage data
    POST /api/approve/{id}        — VP approves a pending_review invoice
    POST /api/reject/{id}         — VP rejects a pending_review invoice
    GET  /api/stats               — counts by status
    WS   /ws/processing           — WebSocket: real-time stage events

Run:
    .venv/bin/uvicorn api:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import invoice_store
import pipeline
import review_queue

UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Galatiq Invoice API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, payload: dict):
        dead = set()
        for ws in self.active:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active.discard(ws)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_serialize(obj):
    """Recursively convert dataclasses / enums to JSON-serializable dicts."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _safe_serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_safe_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if hasattr(obj, "value"):  # Enum
        return obj.value
    return obj


def _stage_data_from_state(state: dict, stage: str) -> dict:
    """Extract serializable data for a given stage from pipeline state."""
    if stage == "ingestion":
        bundle = state.get("invoice")
        if bundle is None:
            return {
                "status": "failed",
                "issues": state.get("ingestion_issues", []),
            }
        inv = bundle.invoice
        return {
            "status": "success",
            "vendor": inv.vendor_name,
            "amount": inv.total,
            "due_date": inv.due_date,
            "invoice_number": inv.invoice_number,
            "line_items": _safe_serialize(bundle.line_items),
            "invoice_date": inv.invoice_date,
        }

    if stage == "validation":
        vr = state.get("validation_result")
        if vr is None:
            return {}
        return {
            "passed": vr.passed,
            "flags": _safe_serialize(vr.flags),
            "item_matches": _safe_serialize(vr.item_matches),
            "arithmetic": _safe_serialize(vr.arithmetic_check),
        }

    if stage == "approval":
        ar = state.get("approval_result")
        if ar is None:
            return {}
        return {
            "decision": ar.decision,
            "risk_score": ar.risk_score,
            "reasoning": ar.final_reasoning,
            "prosecution": ar.prosecution_argument,
            "defense": ar.defense_argument,
            "source": ar.decision_source,
            "llm_recommendation": ar.llm_recommendation,
        }

    if stage == "payment":
        pr = state.get("payment_result")
        if pr is None:
            return {}
        return _safe_serialize(pr)

    return {}


def _build_on_stage_complete(invoice_id: str, loop: asyncio.AbstractEventLoop):
    """Build a synchronous callback that updates invoice_store and queues WS broadcast."""

    def callback(stage: str, state: dict):
        data = _stage_data_from_state(state, stage)

        # Enrich data with top-level fields extracted from ingestion
        if stage == "ingestion" and data.get("status") == "success":
            data["vendor"] = data.get("vendor")
            data["amount"] = data.get("amount")
            data["due_date"] = data.get("due_date")

        # Determine status from state
        status = state.get("status")
        if status:
            data["status"] = status

        # Pick up review_id if set
        if state.get("review_id"):
            data["review_id"] = state["review_id"]

        invoice_store.update_stage(invoice_id, stage, data)

        payload = {
            "invoice_id": invoice_id,
            "stage": stage,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        asyncio.run_coroutine_threadsafe(manager.broadcast(payload), loop)

    return callback


def _run_pipeline_sync(invoice_id: str, file_path: str, loop: asyncio.AbstractEventLoop):
    """Run the pipeline in the thread pool, updating invoice_store at each stage."""
    callback = _build_on_stage_complete(invoice_id, loop)
    try:
        final_state = pipeline.run(
            file_path=file_path,
            on_stage_complete=callback,
        )
        # Ensure final status is recorded
        final_status = final_state.get("status", "error")
        invoice_store.update_stage(invoice_id, "final", {"status": final_status})

        # Broadcast completion
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({
                "invoice_id": invoice_id,
                "stage": "complete",
                "data": {"status": final_status},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
            loop,
        )
    except Exception as exc:
        invoice_store.update_stage(invoice_id, "final", {"status": "error", "error": str(exc)})
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({
                "invoice_id": invoice_id,
                "stage": "error",
                "data": {"status": "error", "error": str(exc)},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
            loop,
        )


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class DecideRequest(BaseModel):
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_invoice(file: UploadFile = File(...)):
    """Upload a single invoice file and kick off background processing."""
    invoice_id = invoice_store.generate_invoice_id()
    filename = file.filename or "invoice.txt"
    dest = UPLOAD_DIR / f"{invoice_id}_{filename}"

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    invoice_store.create_invoice(invoice_id, filename, str(dest))

    loop = asyncio.get_event_loop()
    executor.submit(_run_pipeline_sync, invoice_id, str(dest), loop)

    return {"invoice_id": invoice_id, "status": "processing", "filename": filename}


@app.post("/api/upload/batch")
async def upload_batch(files: list[UploadFile] = File(...)):
    """Upload multiple invoice files and process each in the background."""
    batch_id = str(uuid.uuid4())
    invoice_ids = []
    loop = asyncio.get_event_loop()

    for file in files:
        invoice_id = invoice_store.generate_invoice_id()
        filename = file.filename or "invoice.txt"
        dest = UPLOAD_DIR / f"{invoice_id}_{filename}"

        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        invoice_store.create_invoice(invoice_id, filename, str(dest))
        executor.submit(_run_pipeline_sync, invoice_id, str(dest), loop)
        invoice_ids.append(invoice_id)

    return {
        "batch_id": batch_id,
        "total_files": len(invoice_ids),
        "invoice_ids": invoice_ids,
        "status": "processing",
    }


@app.get("/api/invoices")
def list_invoices(status: Optional[str] = None, vendor: Optional[str] = None):
    """List all invoices, optionally filtered by status and/or vendor."""
    return invoice_store.list_invoices(status=status, vendor=vendor)


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    """Get full invoice detail including all stage data."""
    inv = invoice_store.get_invoice(invoice_id)
    if inv is None:
        raise HTTPException(404, f"Invoice {invoice_id} not found")

    # Merge review queue data if pending_review
    if inv.get("review_id"):
        review = review_queue.get_review(inv["review_id"])
        if review:
            inv["review_data"] = review

    return inv


@app.post("/api/approve/{invoice_id}")
def approve_invoice(invoice_id: str, body: DecideRequest):
    """VP approves a pending_review invoice."""
    inv = invoice_store.get_invoice(invoice_id)
    if inv is None:
        raise HTTPException(404, f"Invoice {invoice_id} not found")
    if inv.get("status") != "pending_review":
        raise HTTPException(400, f"Invoice {invoice_id} is not pending review (status={inv.get('status')})")

    review_id = inv.get("review_id")
    if not review_id:
        raise HTTPException(400, "No review_id found for this invoice")

    try:
        review_queue.decide(review_id=review_id, decision="APPROVED", reasoning=body.reasoning)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    invoice_store.update_stage(invoice_id, "payment", {"status": "paid"})

    # Broadcast
    asyncio.get_event_loop().create_task(manager.broadcast({
        "invoice_id": invoice_id,
        "stage": "approved",
        "data": {"status": "paid", "reasoning": body.reasoning},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    return invoice_store.get_invoice(invoice_id)


@app.post("/api/reject/{invoice_id}")
def reject_invoice(invoice_id: str, body: DecideRequest):
    """VP rejects a pending_review invoice."""
    inv = invoice_store.get_invoice(invoice_id)
    if inv is None:
        raise HTTPException(404, f"Invoice {invoice_id} not found")
    if inv.get("status") != "pending_review":
        raise HTTPException(400, f"Invoice {invoice_id} is not pending review (status={inv.get('status')})")

    review_id = inv.get("review_id")
    if not review_id:
        raise HTTPException(400, "No review_id found for this invoice")

    try:
        review_queue.decide(review_id=review_id, decision="REJECTED", reasoning=body.reasoning)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    invoice_store.update_stage(invoice_id, "payment", {"status": "rejected"})

    asyncio.get_event_loop().create_task(manager.broadcast({
        "invoice_id": invoice_id,
        "stage": "rejected",
        "data": {"status": "rejected", "reasoning": body.reasoning},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    return invoice_store.get_invoice(invoice_id)


@app.get("/api/stats")
def stats():
    """Return invoice counts by status."""
    return invoice_store.get_stats()


# ---------------------------------------------------------------------------
# Legacy review endpoints (keep for backwards compatibility)
# ---------------------------------------------------------------------------

@app.get("/api/reviews")
def list_reviews(status: Optional[str] = None):
    if status and status not in ("pending", "approved", "rejected"):
        raise HTTPException(400, "status must be pending, approved, or rejected")
    return review_queue.list_reviews(status=status)


@app.get("/api/reviews/{review_id}")
def get_review(review_id: str):
    review = review_queue.get_review(review_id)
    if review is None:
        raise HTTPException(404, f"Review {review_id} not found")
    return review


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/processing")
async def ws_processing(websocket: WebSocket):
    """WebSocket endpoint — broadcasts stage events to all connected clients."""
    await manager.connect(websocket)
    try:
        # Keep connection alive; client may send invoice_id filter (ignored for now)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
