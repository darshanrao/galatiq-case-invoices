"""
FastAPI application entry point — invoice processing pipeline + dashboard API.

Run:
    uvicorn src.api.app:app --reload --port 8000
"""

from __future__ import annotations

import sys
import pathlib

# Ensure project root is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

from src.core.logging_config import configure_logging

load_dotenv()
configure_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router

app = FastAPI(title="Galatiq Invoice API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
