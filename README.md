# Galatiq Case: Invoice Processing Automation

## Background

Acme Corp is a PE-backed manufacturing firm losing **$2M/year** on manual invoice processing. Invoices arrive via email as PDFs in messy formats with frequent errors. Staff manually extract data, validate against a legacy inventory database, obtain VP approval via email chains, and process payment via a banking API.

**Pain points eliminated by this system:**
- 30% error rate → deterministic + LLM extraction with structured validation
- 5-day processing delays → sub-minute end-to-end pipeline
- No audit trail → every stage logged with reasoning
- Duplicate payments → content-fingerprint deduplication across sessions

---

## System Overview

A **LangGraph-orchestrated multi-agent pipeline** that ingests invoice files in any format, validates them against inventory, applies tiered approval logic, and surfaces approved invoices to a finance dashboard for manual payment authorization. The system mirrors a real enterprise AP workflow where approval and disbursement are separate responsibilities.

```
Upload → Ingest → Validate → Approve ──────────────────→ [APPROVED] → Finance pays via dashboard
                                     └→ [PENDING_REVIEW] → Human VP reviews in dashboard
                                     └→ [REJECTED]       → Logged with structured reasoning
```

---

## Architecture

### Module Structure

```
galatiq-case-invoices/
├── src/
│   ├── core/
│   │   ├── models.py          # All dataclasses: Invoice, InvoiceBundle, ValidationResult, etc.
│   │   ├── exceptions.py      # IngestionError, LLMConfigurationError, VisionConfigurationError
│   │   └── logging_config.py  # Structured log formatting
│   │
│   ├── ingestion/
│   │   ├── service.py         # Orchestrates: deterministic → LLM fallback → vision fallback
│   │   ├── parsers/           # Format-specific parsers: JSON, CSV, XML, TXT
│   │   ├── normalizer.py      # Date, invoice number, item name, tax rate normalization
│   │   ├── read_file.py       # File type detection (PDF, scanned_pdf, image, txt, csv, etc.)
│   │   ├── llm_extract.py     # Grok (grok-3-mini) extraction from unstructured text
│   │   └── vision_extract.py  # Grok Vision extraction from images and scanned PDFs
│   │
│   ├── validation/
│   │   ├── service.py         # Orchestrates all validation checks, returns ValidationResult
│   │   └── arithmetic.py      # Line-item math verification (subtotal, tax, total)
│   │
│   ├── approval/
│   │   ├── service.py         # 4-tier approval: fraud auto-reject → deterministic → precedent → LLM+human
│   │   └── fraud_detection.py # Suspicious vendor keywords, urgency phrases, indicator counting
│   │
│   ├── pipeline/
│   │   ├── graph.py           # LangGraph StateGraph: nodes, conditional edges, routing functions
│   │   ├── runner.py          # run() entry point, graph singleton, stage callbacks
│   │   └── payment.py         # pay() mock ACH gateway, reject() structured rejection builder
│   │
│   ├── persistence/
│   │   ├── inventory_db.py    # Inventory lookups, fuzzy matching, duplicate detection
│   │   ├── invoice_store.py   # SQLite store for all invoice state (per-stage data)
│   │   ├── review_queue.py    # Human review queue with decide() for VP approve/reject
│   │   └── precedent_db.py    # Approval precedent store for Tier 2.5 self-correction
│   │
│   └── api/
│       ├── app.py             # FastAPI application, CORS, router registration
│       ├── routes.py          # REST endpoints: upload, list, approve, reject, pay, stats
│       ├── websocket.py       # WebSocket connection manager, stage-complete broadcaster
│       └── serialization.py   # State → JSON serialization for API responses
│
├── cli/
│   ├── main.py                # Single-invoice CLI runner with formatted output
│   ├── extract_to_json.py     # Batch extraction → data/normalized/*.json
│   └── clean_databases.py     # Reset all processing DBs (preserves inventory stock)
│
├── dashboard/                 # Next.js 15 + TailwindCSS frontend
│   ├── app/                   # App Router pages
│   ├── components/            # UI: UploadZone, InvoiceTable, InvoiceDetail, ProcessingModal, PaymentGateway, etc.
│   ├── hooks/                 # useInvoices, useUpload, useWebSocket, usePay
│   └── types/                 # TypeScript invoice types
│
├── scripts/
│   ├── run_all.py             # Batch CLI runner over all test invoices
│   ├── check_dependencies.py  # Verify all optional dependencies
│   └── check_llm.py           # Verify Grok API connectivity
│
├── tests/
│   ├── unit/                  # Parser, normalizer, validation, approval, payment, DB tests
│   └── integration/           # E2E pipeline tests with mocked LLM
│
└── data/
    ├── invoices/              # 18 test invoices: TXT, JSON, CSV, XML, PDF, PNG
    └── normalized/            # Canonical JSON output from extract_to_json.py
```

---

## How Each Module Was Built

### 1. Ingestion — Tiered Extraction

**Problem:** Invoices arrive in at least 6 different formats (TXT, JSON, CSV, XML, PDF, scanned PDF, image). The data is messy — inconsistent field names, missing values, varying date formats, typos in item names.

**Solution — three-tier extraction:**

```
Tier 1: Deterministic parsers (src/ingestion/parsers/)
         → Fast, zero cost, handles well-structured files
         → Falls through if critical fields (invoice_number, line_items, total) are missing

Tier 2: LLM extraction (src/ingestion/llm_extract.py)
         → Grok grok-3-mini with structured JSON prompt
         → Runs on freeform text (TXT, PDF) always; runs on structured formats only if Tier 1 failed
         → Targeted extraction: passes only missing fields to minimize token usage

Tier 3: Vision extraction (src/ingestion/vision_extract.py)
         → Grok Vision for JPEG/PNG image invoices
         → For scanned PDFs: PyMuPDF renders pages → temporary PNGs → vision extraction
         → Multi-page: each page extracted separately, results merged
```

**Normalization** (`src/ingestion/normalizer.py`) runs after extraction regardless of tier:
- Invoice numbers → `INV-XXXX` format
- Dates → `YYYY-MM-DD` ISO format
- Item names → title-cased, whitespace collapsed (e.g. `Widget A` → `WidgetA`)
- Tax rates → decimal fraction (e.g. `8%` → `0.08`)

### 2. Validation — Rule-Based Checks

**File:** `src/validation/service.py`

Seven checks run in order. Each produces a `Flag` with severity `HARD_FAIL` or `WARNING`:

| Check | Severity | Trigger |
|---|---|---|
| Empty vendor | HARD_FAIL | vendor_name blank |
| Negative quantity | HARD_FAIL | any line item qty < 0 |
| Fraud item | HARD_FAIL | item in known fraud list (e.g. FakeItem) |
| Unknown item | HARD_FAIL | item not in inventory + no fuzzy match |
| Stock exceeded | HARD_FAIL | requested qty > available stock |
| Zero stock item | WARNING | stock = 0 (item exists, just depleted) |
| Currency mismatch | WARNING | currency ≠ USD |
| Arithmetic mismatch | WARNING | computed total ≠ claimed total (±$0.02 tolerance) |
| Duplicate invoice | WARNING | same invoice number OR same vendor+amount+date seen before |

**Fuzzy matching** (`inventory_db.fuzzy_match_item`): two-step approach — first collapses spaces for OCR artifacts (e.g. `Widget A` → `WidgetA`), then runs `difflib.SequenceMatcher` at 0.9 similarity threshold.

**Duplicate detection** uses two complementary methods:
1. Invoice number match — catches exact re-submissions
2. Content fingerprint (SHA256 of `vendor|amount|date`) — catches same invoice submitted with a different file format or ID

Any `HARD_FAIL` → invoice fails validation and is rejected. `WARNING` flags pass validation but feed into the approval tier.

### 3. Approval — 4-Tier Decision Engine

**File:** `src/approval/service.py`

Designed to minimize LLM calls and maximize consistency. Tiers run in order and short-circuit:

**Tier 1 — Fraud auto-reject (deterministic, zero LLM calls)**
Checks for suspicious vendor keywords ("urgent", "immediate payment", "wire transfer required"), extreme price multipliers, and structural anomalies. ≥2 fraud indicators → `REJECTED` immediately.

**Tier 2 — Deterministic rules (zero LLM calls)**
Zero warnings + zero fraud indicators → `APPROVED` automatically. Clean invoices never touch the LLM.

**Tier 2.5 — Precedent self-correction (zero LLM calls)**
Looks up the invoice's `flag_pattern` (sorted set of WARNING categories) in `precedent.db`. If the same pattern has been seen ≥3 times with a consistent human decision → apply that decision automatically. This is the **self-correction loop**: the system gets smarter from VP decisions without retraining.

**Tier 3 — LLM risk scoring → human review**
One structured Grok call returns `{ risk_score, recommendation, explanation }`. The system always routes to `PENDING_REVIEW` (never auto-decides from LLM alone). The VP's decision is recorded via `precedent_db.record_human_override()`, feeding Tier 2.5 for future runs.

Currency mismatch always bypasses Tier 2.5 (exchange rate risk requires fresh human judgment each time).

### 4. Payment — Human-in-the-Loop

**Design decision:** Approval and disbursement are separate responsibilities in real enterprise AP. The pipeline stops at `status="approved"`. The finance team authorizes payment via the dashboard's **Pay Now** button, which opens a payment confirmation modal showing vendor, amount, and ACH method before executing.

**File:** `src/pipeline/payment.py`

`mock_payment()` generates a realistic `TXN-XXXXXXXXXX` transaction ID, ISO timestamp, and `ACH` method — matching what a real payment gateway returns. In production, this would call a banking API (ACH, SWIFT, etc.).

**Rejection** (`reject()`) builds a structured rejection regardless of which stage failed, capturing the stage name and human-readable reason for the audit log.

### 5. LangGraph Pipeline

**File:** `src/pipeline/graph.py`

The pipeline is a `StateGraph` over `InvoiceState` (a `TypedDict`). Each node returns a partial state update; LangGraph merges these into the running state.

```
START → ingest ──[success]──→ validate ──[passed]──→ approve ──[APPROVED]──→ approved → END
          └──[fail, retry]──┘             └──[failed]──→ reject → END         └──[PENDING_REVIEW]──→ queue_for_review → END
          └──[fail, max retries]──→ reject → END                              └──[REJECTED]──→ reject → END
```

**Retry logic:** ingestion retries up to `MAX_INGEST_ATTEMPTS=2` before routing to reject. This handles transient LLM failures.

**Stage callbacks:** the runner registers `on_stage_complete` before each run. After every node, `_notify()` fires the callback — used by the API to broadcast WebSocket events to the dashboard in real time.

### 6. Persistence Layer

Four SQLite databases, each with a single responsibility:

| Database | Purpose |
|---|---|
| `inventory.db` | Inventory stock levels + processed invoice tracking (duplicate detection) |
| `invoice_store.db` | All invoice state: per-stage data, status, timestamps |
| `review_queue.db` | Pending/decided human review items |
| `precedent.db` | Approval decisions by flag pattern for Tier 2.5 learning |

All databases are created automatically on first run. The `processed_invoices` table in `inventory.db` stores only duplicate-tracking data — the `inventory` table (stock levels) is never modified by the pipeline.

### 7. API Layer

**File:** `src/api/routes.py` (FastAPI)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload single invoice → background processing |
| `POST` | `/api/upload/batch` | Upload multiple invoices → sequential processing |
| `GET` | `/api/invoices` | List all invoices (filterable by status, vendor) |
| `GET` | `/api/invoices/{id}` | Full invoice detail including all stage data |
| `POST` | `/api/approve/{id}` | VP approves a pending_review invoice |
| `POST` | `/api/reject/{id}` | VP rejects a pending_review invoice |
| `POST` | `/api/pay/{id}` | Finance team authorizes payment for approved invoice |
| `GET` | `/api/stats` | Invoice counts by status |
| `GET` | `/api/reviews` | List human review queue |
| `WS` | `/ws/processing` | Real-time stage updates via WebSocket |

Pipeline runs in a `ThreadPoolExecutor` so it doesn't block the async event loop. WebSocket broadcasts are sent from the thread via `asyncio.run_coroutine_threadsafe`.

### 8. Dashboard

**Stack:** Next.js 15, TailwindCSS, TanStack Query, WebSocket

Key UX decisions:
- **Real-time processing modal** — shows each pipeline stage (ingestion, validation, approval, payment) completing live via WebSocket, with color-coded status (green=done, red=failed, blue=awaiting, gray=skipped)
- **Separate approval and payment flows** — VP reviews flagged invoices from the review queue with AI reasoning visible; finance team pays from the invoice detail view with payment gateway modal
- **Receipt invoice number as primary ID** — shows the actual invoice number from the document (e.g. `INV-1001`), not the internal system ID
- **Stats bar** — live counts for Processing, Pending Review, Awaiting Payment, Paid, Rejected

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for dashboard)
- xAI API key (for LLM and vision extraction)

### Backend Setup

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add your XAI_API_KEY

# 4. Initialize inventory database (run once)
python -c "from src.persistence.inventory_db import init_inventory_db; init_inventory_db()"
```

### Dashboard Setup

```bash
cd dashboard
npm install
# .env.local already points to http://localhost:8000
```

---

## Running the System

### Option A: Dashboard (recommended)

Start both servers and use the web UI:

```bash
# Terminal 1 — API server
uvicorn src.api.app:app --reload --port 8000

# Terminal 2 — Dashboard
cd dashboard && npm run dev
```

Open `http://localhost:3000`. Drag and drop any invoice file to process it. Watch live stage updates. Review flagged invoices. Pay approved invoices.

### Option B: CLI (single invoice)

```bash
.venv/bin/python cli/main.py --invoice_path data/invoices/invoice_1001.txt
```

Sample output:
```
--- Invoice: INV-1001 ---
Vendor : Acme Supplies Ltd.
Total  : $1,250.00
Items  : 3

--- Validation: PASSED ---
  Arithmetic: computed=$1,250.00  claimed=$1,250.00  OK

--- Approval: APPROVED ---
  Source     : deterministic
  Reasoning  : Automatically approved: invoice passed all checks with no warnings.

Final status: APPROVED
```

### Option C: Batch CLI (all invoices)

```bash
.venv/bin/python scripts/run_all.py
```

### Option D: Extract to canonical JSON

```bash
.venv/bin/python cli/extract_to_json.py
# Output: data/normalized/*.json
```

---

## Test Invoices

The `data/invoices/` directory contains 18 invoices that cover every code path:

| Invoice | Format | What it tests |
|---|---|---|
| 1001 | TXT | Clean invoice — auto-approved |
| 1002 | TXT | GadgetX quantity exceeds stock (5 in stock, 20 requested) |
| 1003 | TXT | FakeItem — known fraud item, hard fail |
| 1004 | JSON | Clean JSON — auto-approved |
| 1004_revised | JSON | Same invoice number, revision field set — duplicate detection |
| 1005 | JSON | High-value invoice — LLM risk scoring, pending review |
| 1006 | CSV | Clean CSV — auto-approved |
| 1007 | CSV | Currency mismatch (EUR) — warning, routed to human review |
| 1008 | TXT | Unknown items (SuperGizmo, MegaSprocket) — not in inventory |
| 1009 | JSON | Negative quantity — hard fail |
| 1010 | TXT | Freeform TXT — LLM extraction required |
| 1011 | PDF | Searchable PDF — pdfplumber text extraction |
| 1012 | PDF | Another searchable PDF |
| 1013 | PDF | PDF requiring LLM fallback |
| 1014 | XML | XML format parser |
| 1015 | CSV | Additional CSV test |
| 1016 | JSON | WidgetC — unknown item not in inventory |
| 1017 | PNG | Image invoice — Grok Vision extraction |
| 1018 | PDF | Scanned PDF — PyMuPDF → PNG → Grok Vision |

---

## Running Tests

```bash
# All tests
.venv/bin/pytest tests/ -v

# Unit tests only
.venv/bin/pytest tests/unit/ -v

# Integration tests only (requires XAI_API_KEY; LLM calls mocked by default)
.venv/bin/pytest tests/integration/ -v
```

Tests cover: parsers, normalizer, arithmetic, validation rules, fraud detection, approval tiers, payment, inventory DB, precedent DB, review queue, graph routing, and E2E pipeline with mocked LLM.

---

## Database Management

### Clean all processing data (fresh start)

Clears invoice history, review queue, approval precedents, and duplicate-detection records. **Does not touch inventory stock levels.**

```bash
.venv/bin/python cli/clean_databases.py          # Prompts for confirmation
.venv/bin/python cli/clean_databases.py --yes    # Skip confirmation
.venv/bin/python cli/clean_databases.py --dry-run # Preview without changes
```

### Re-initialize inventory

```bash
python -c "from src.persistence.inventory_db import init_inventory_db; init_inventory_db()"
```

---

## Evaluation Criteria — How We Address Each

### Functionality — End-to-End

Every invoice in `data/invoices/` processes through the full pipeline. Edge cases handled: all 6 file formats, scanned PDFs, image invoices, duplicate submissions, negative quantities, unknown items, fraud items, currency mismatches, arithmetic errors, and missing critical fields.

### Code Quality

- **Modular structure**: each concern in its own module — ingestion, validation, approval, payment, persistence, API, CLI all separated
- **Typed throughout**: dataclasses for all domain objects (`Invoice`, `InvoiceBundle`, `ValidationResult`, `ApprovalResult`, `PaymentResult`), `TypedDict` for pipeline state
- **Error handling**: every stage catches and surfaces structured errors; LLM failures fall back gracefully; never crashes the pipeline
- **Structured logging**: `structlog`-style formatted output at every stage with severity levels
- **Testable**: pure functions throughout, dependency injection for DB paths, LLM mocked in tests

### Agentic Sophistication

- **Multi-agent orchestration**: LangGraph `StateGraph` with conditional routing across 6 nodes
- **Structured LLM outputs**: both ingestion and approval use JSON-schema prompts with retry logic and graceful fallback
- **Self-correction loop (Tier 2.5)**: the system learns from VP decisions via `precedent.db` — the same invoice pattern approved 3 times is auto-approved in future without human intervention
- **Tool use**: LLM-based ingestion is a tool call; vision extraction uses multimodal Grok; approval scoring returns structured JSON
- **Retry with backoff**: `invoke_with_retry()` handles rate limits and transient API errors with exponential backoff
- **Ingestion retry loop**: failed ingestion retries up to 2 times before routing to rejection

### Shipping Mindset

- Working prototype with real file uploads, real-time UI, and real LLM calls on day one
- Scope decisions: mock payment gateway (realistic output, real transaction IDs) instead of actual banking API integration; SQLite instead of Postgres (zero infrastructure)
- Human-in-the-loop design reflects actual enterprise AP workflow — approval and payment as separate steps

### Above and Beyond

- **Vision extraction**: handles image invoices (PNG/JPEG) and scanned PDFs via Grok Vision — not in the original spec
- **Real-time WebSocket dashboard**: live stage-by-stage progress as invoices process — not in the original spec
- **Content fingerprint deduplication**: catches duplicate invoices submitted with different invoice numbers by hashing vendor+amount+date — more robust than invoice-number-only matching
- **Precedent-based self-correction**: the system gets smarter with use — learned decisions from VP reduce LLM calls over time
- **Batch upload**: process multiple invoices in one API call
- **Fuzzy item matching**: OCR artifacts and minor typos (e.g. `Widget A` vs `WidgetA`) still match correctly
- **Arithmetic verification**: independently recomputes subtotal → tax → total and flags discrepancies

### UI/UX

- Drag-and-drop file upload with batch support
- Live processing modal with per-stage status indicators (green/red/blue/gray)
- Invoice detail view showing all stage data: extracted fields, validation flags with severity, approval reasoning, payment receipt
- Payment gateway modal for finance team with confirmation step before executing
- Stats bar showing counts by status (Processing, Pending Review, Awaiting Payment, Paid, Rejected)
- Status badges differentiate "Awaiting Payment" (blue) from "Paid" (green) from "Pending Review" (yellow)

---

## Dependency Notes

- **PyMuPDF (`fitz`)**: required for scanned PDF extraction. Included in `requirements.txt`.
- **pdfplumber**: required for text-based PDF extraction. Included in `requirements.txt`.
- **langchain-openai**: required for LLM integration (uses OpenAI-compatible xAI endpoint). Included in `requirements.txt`.

Verify all dependencies:
```bash
.venv/bin/python scripts/check_dependencies.py
.venv/bin/python scripts/check_llm.py   # Tests live API connectivity
```

**Use the project venv** — system Python (e.g. Anaconda) may have conflicting `langchain` versions that cause `LangSmithParams` import errors.
