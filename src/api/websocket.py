"""WebSocket connection manager and stage-complete callback builder."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Set

from fastapi import WebSocket

from src.api.serialization import _stage_data_from_state
from src.persistence import invoice_store


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


def _build_on_stage_complete(invoice_id: str, loop: asyncio.AbstractEventLoop):
    """Build a synchronous callback that updates invoice_store and queues WS broadcast."""

    def callback(stage: str, state: dict):
        data = _stage_data_from_state(state, stage)

        if stage == "ingestion" and data.get("status") == "success":
            data["vendor"] = data.get("vendor")
            data["amount"] = data.get("amount")
            data["due_date"] = data.get("due_date")

        status = state.get("status")
        if status:
            data["status"] = status

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
