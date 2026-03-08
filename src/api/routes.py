"""FastAPI route handlers for the invoice processing API."""

from __future__ import annotations

import asyncio
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.persistence import invoice_store, review_queue
from src.pipeline.runner import run as pipeline_run
from src.pipeline.payment import pay as run_payment, reject as run_reject
from src.api.websocket import manager, _build_on_stage_complete

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=4)

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DecideRequest(BaseModel):
    reasoning: str = ""


def _run_pipeline_sync(invoice_id: str, file_path: str, loop: asyncio.AbstractEventLoop):
    """Run the pipeline in the thread pool, updating invoice_store at each stage."""
    callback = _build_on_stage_complete(invoice_id, loop)
    try:
        final_state = pipeline_run(
            file_path=file_path,
            on_stage_complete=callback,
        )
        final_status = final_state.get("status", "error")
        invoice_store.update_stage(invoice_id, "final", {"status": final_status})

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


@router.post("/api/upload")
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


@router.post("/api/upload/batch")
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


@router.get("/api/invoices")
def list_invoices(status: Optional[str] = None, vendor: Optional[str] = None):
    """List all invoices, optionally filtered by status and/or vendor."""
    return invoice_store.list_invoices(status=status, vendor=vendor)


@router.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    """Get full invoice detail including all stage data."""
    inv = invoice_store.get_invoice(invoice_id)
    if inv is None:
        raise HTTPException(404, f"Invoice {invoice_id} not found")

    if inv.get("review_id"):
        review = review_queue.get_review(inv["review_id"])
        if review:
            inv["review_data"] = review

    return inv


@router.post("/api/approve/{invoice_id}")
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

    # Human reviewer approved — invoice is now awaiting payment authorization
    invoice_store.update_stage(invoice_id, "approval", {"status": "approved", "reasoning": body.reasoning})

    asyncio.get_event_loop().create_task(manager.broadcast({
        "invoice_id": invoice_id,
        "stage": "approved",
        "data": {"status": "approved", "reasoning": body.reasoning},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    return invoice_store.get_invoice(invoice_id)


@router.post("/api/reject/{invoice_id}")
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


@router.post("/api/pay/{invoice_id}")
async def pay_invoice(invoice_id: str):
    """Finance team authorizes payment for an approved invoice."""
    inv = invoice_store.get_invoice(invoice_id)
    if inv is None:
        raise HTTPException(404, f"Invoice {invoice_id} not found")
    if inv.get("status") != "approved":
        raise HTTPException(400, f"Invoice {invoice_id} cannot be paid (status={inv.get('status')})")

    # Reconstruct minimal state so pay() can run
    import json
    from src.core.models import InvoiceBundle, Invoice as InvoiceModel, LineItem

    ingestion_raw = inv.get("ingestion_data") or {}
    if isinstance(ingestion_raw, str):
        ingestion_raw = json.loads(ingestion_raw)

    line_items = [
        LineItem(
            item=li.get("item", ""),
            quantity=li.get("quantity", 0),
            unit_price=li.get("unit_price", 0.0),
            line_total=li.get("line_total"),
        )
        for li in (ingestion_raw.get("line_items") or [])
    ]
    invoice_model = InvoiceModel(
        invoice_number=ingestion_raw.get("invoice_number") or invoice_id,
        vendor_name=inv.get("vendor") or ingestion_raw.get("vendor") or "Unknown",
        total=inv.get("amount"),
    )
    bundle = InvoiceBundle(invoice=invoice_model, line_items=line_items)
    state = {"invoice": bundle, "audit_log": [], "status": "approved"}

    payment_result = run_payment(state)
    pr = payment_result["payment_result"]

    payment_data = {
        "status": "paid",
        "vendor": pr.vendor,
        "amount": pr.amount,
        "transaction_id": pr.transaction_id,
        "paid_at": pr.paid_at,
        "payment_method": pr.payment_method,
    }
    invoice_store.update_stage(invoice_id, "payment", payment_data)

    await manager.broadcast({
        "invoice_id": invoice_id,
        "stage": "payment",
        "data": {"status": "paid"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return invoice_store.get_invoice(invoice_id)


@router.get("/api/stats")
def stats():
    """Return invoice counts by status."""
    return invoice_store.get_stats()


@router.get("/api/reviews")
def list_reviews(status: Optional[str] = None):
    if status and status not in ("pending", "approved", "rejected"):
        raise HTTPException(400, "status must be pending, approved, or rejected")
    return review_queue.list_reviews(status=status)


@router.get("/api/reviews/{review_id}")
def get_review(review_id: str):
    review = review_queue.get_review(review_id)
    if review is None:
        raise HTTPException(404, f"Review {review_id} not found")
    return review


@router.websocket("/ws/processing")
async def ws_processing(websocket: WebSocket):
    """WebSocket endpoint — broadcasts stage events to all connected clients."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
