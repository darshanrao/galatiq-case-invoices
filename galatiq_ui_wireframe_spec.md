# Galatiq Invoice Processing Automation - UI Wireframe Specification

## Overview
A two-role dashboard application for automating invoice processing. Primary users: AP Clerks (upload & monitor) and VPs (approve/reject). The system provides real-time visibility into a 4-stage agentic pipeline: Ingestion → Validation → Approval → Payment.

---

## Design Principles

1. **Transparency First**: Every agent decision must be visible with clear reasoning
2. **Real-Time Feedback**: Show live processing status, not static states
3. **Error-Friendly**: 30% error rate means failures are normal, not exceptional
4. **Role-Based Views**: Same dashboard, different primary actions per role
5. **Speed & Efficiency**: Replace 5-day delays with instant visibility

---

## Color System

```
Primary Blue: #2563eb (actions, links)
Success Green: #10b981 (approved, completed)
Warning Orange: #f59e0b (needs attention, approval required)
Error Red: #ef4444 (rejected, failed validation)
Neutral Gray: #6b7280 (text, borders)
Background: #f9fafb (page background)
Card White: #ffffff (content cards)
Processing Purple: #8b5cf6 (in-progress states)
```

---

## Layout Structure

### Global Layout
```
┌─────────────────────────────────────────────────────────────────────┐
│ Header (fixed, 64px height)                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Main Content Area (scrollable)                                    │
│                                                                     │
│                                                                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Header Components:**
- Left: Logo + App Name "Galatiq Invoice Automation"
- Right: Role Selector Dropdown + Settings Icon

---

## Screen 1: Main Dashboard (Default View)

### A. Header Stats Bar
```
┌────────────────────────────────────────────────────────────────┐
│  Today's Stats (4 stat cards, horizontal)                      │
│  ┌──────────┬──────────┬──────────┬──────────┐                │
│  │ 🔄       │ ⚠️       │ ✅       │ ❌       │                │
│  │ Processing│ Needs    │ Auto-    │ Rejected │                │
│  │ 3        │ Approval │ Approved │ 2        │                │
│  │          │ 5        │ 12       │          │                │
│  └──────────┴──────────┴──────────┴──────────┘                │
└────────────────────────────────────────────────────────────────┘
```

**Stat Card Design:**
- Icon (emoji or Lucide icon)
- Label (12px, gray)
- Count (24px, bold, colored by status)
- Clickable → filters invoice list below

---

### B. Upload Section (AP Clerk Primary Action)

```
┌────────────────────────────────────────────────────────────────┐
│  📤 Upload Invoices                                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                                                          │  │
│  │           Drag & drop PDF, TXT, CSV, JSON here          │  │
│  │                  or click to browse                      │  │
│  │                                                          │  │
│  │              Supported: PDF, TXT, CSV, JSON             │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  [📁 Upload Folder (Batch)]   [Clear Queue]                   │
└────────────────────────────────────────────────────────────────┘
```

**Upload Zone Specifications:**
- Dashed border (2px, #d1d5db)
- Background: #f9fafb
- Height: 180px
- Hover state: border changes to primary blue, background to #eff6ff
- Active drag state: border solid blue, background #dbeafe
- Button styling: Primary blue button with folder icon

---

### C. Invoice List Table

```
┌────────────────────────────────────────────────────────────────────────────┐
│  📋 Recent Invoices                               [🔍 Search] [Filter ▾]  │
├────────┬─────────────────┬──────────┬─────────────┬──────────────┬────────┤
│ ID     │ Vendor          │ Amount   │ Due Date    │ Status       │ Action │
├────────┼─────────────────┼──────────┼─────────────┼──────────────┼────────┤
│ 1008   │ SuperTech Inc.  │ $15,240  │ Mar 15      │ ⚠️ Needs     │ [View] │
│        │                 │          │             │   Approval   │        │
├────────┼─────────────────┼──────────┼─────────────┼──────────────┼────────┤
│ 1007   │ Acme Supplies   │ $3,450   │ Mar 10      │ ✅ Auto-     │ [View] │
│        │                 │          │             │   Approved   │        │
├────────┼─────────────────┼──────────┼─────────────┼──────────────┼────────┤
│ 1006   │ Widget Co.      │ $8,900   │ Mar 12      │ 🔄 Processing│ [View] │
│        │                 │          │             │              │        │
├────────┼─────────────────┼──────────┼─────────────┼──────────────┼────────┤
│ 1003   │ Sketchy Vendor  │ $50,000  │ Mar 8       │ ❌ Rejected  │ [View] │
│        │                 │          │             │              │        │
└────────┴─────────────────┴──────────┴─────────────┴──────────────┴────────┘
```

**Table Specifications:**
- Zebra striping (alternate rows #f9fafb)
- Hover: entire row highlights with #f3f4f6
- Status badges:
  - Processing: Purple background #ede9fe, purple text
  - Needs Approval: Orange background #fef3c7, orange text
  - Auto-Approved: Green background #d1fae5, green text
  - Rejected: Red background #fee2e2, red text
- Action button: Secondary blue button, opens detail modal
- Sortable columns (click header to sort)

---

## Screen 2: Live Processing Modal

Triggered when clicking "View" on a processing invoice or immediately after upload.

```
┌──────────────────────────────────────────────────────────────────┐
│  Processing: invoice_1008.pdf                          [✕ Close] │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ✅ Stage 1: Ingestion                    Completed in 0.8s │ │
│  │                                                            │ │
│  │ Extracted Data:                                            │ │
│  │ • Vendor: SuperTech Inc.                                   │ │
│  │ • Amount: $15,240.00                                       │ │
│  │ • Items:                                                   │ │
│  │   - 2× SuperGizmo                                          │ │
│  │   - 3× MegaSprocket                                        │ │
│  │ • Due Date: March 15, 2026                                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 🔄 Stage 2: Validation                    In progress...   │ │
│  │                                                            │ │
│  │ Checking inventory database...                            │ │
│  │ ⚠️ SuperGizmo: NOT FOUND in inventory                      │ │
│  │ ⚠️ MegaSprocket: NOT FOUND in inventory                    │ │
│  │                                                            │ │
│  │ [View Full Validation Report]                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ⏸️ Stage 3: Approval                      Waiting...       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ⏸️ Stage 4: Payment                       Waiting...       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  [View Original PDF]                         [Cancel Processing]│
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Stage Card Specifications:**
- Border-left: 4px colored indicator
  - Green (#10b981): Completed
  - Purple (#8b5cf6): In progress (with animated pulse)
  - Gray (#d1d5db): Waiting
  - Red (#ef4444): Failed
- Padding: 16px
- Margin between stages: 12px
- Expandable/collapsible for completed stages (show/hide details)
- Duration shown in top-right (gray, 12px)

**Animation:**
- In-progress stages have a subtle pulse animation
- Stage transitions: smooth accordion expand/collapse
- Progress indicator: rotating spinner icon for active stage

---

## Screen 3: Approval Queue (VP View)

```
┌──────────────────────────────────────────────────────────────────┐
│  Approval Queue (5 items pending)                  [Sort by ▾]  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ INV-1008 • SuperTech Inc. • $15,240 • Due: Mar 15          │ │
│  │ ⚠️ Flagged: Unknown items in order                         │ │
│  │                                                            │ │
│  │ Extracted Data:                                            │ │
│  │ • Vendor: SuperTech Inc.                                   │ │
│  │ • Total Amount: $15,240.00                                 │ │
│  │ • Line Items:                                              │ │
│  │   - 2× SuperGizmo @ $5,000 = $10,000                       │ │
│  │   - 3× MegaSprocket @ $1,747 = $5,240                      │ │
│  │ • Due Date: March 15, 2026                                 │ │
│  │                                                            │ │
│  │ ❌ Validation Issues (2):                                   │ │
│  │ • SuperGizmo: Not found in inventory database              │ │
│  │ • MegaSprocket: Not found in inventory database            │ │
│  │                                                            │ │
│  │ 🤖 Agent Reasoning:                                         │ │
│  │ "Invoice exceeds $10,000 threshold and references items    │ │
│  │  not currently in our inventory system. Manual review      │ │
│  │  recommended to verify vendor legitimacy and item codes."  │ │
│  │                                                            │ │
│  │ [📄 View PDF]  [✅ Approve]  [❌ Reject]  [💬 Add Note]    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  [Next invoice in queue...]                                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Approval Card Specifications:**
- White background with subtle shadow
- Padding: 24px
- Border-left: 4px orange (#f59e0b) for pending items
- Sections clearly separated with light gray dividers
- Validation issues in red alert box (#fee2e2 background)
- Agent reasoning in blue info box (#dbeafe background)
- Action buttons:
  - Approve: Green (#10b981)
  - Reject: Red (#ef4444)
  - Secondary actions: Gray outline buttons

---

## Screen 4: Invoice Detail View (Approved/Rejected)

### Approved Invoice
```
┌──────────────────────────────────────────────────────────────────┐
│  ✅ INV-1007 - Approved                                [✕ Close]│
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Invoice Details:                                                │
│  • Vendor: Acme Supplies Corp.                                   │
│  • Amount: $3,450.00                                             │
│  • Due Date: March 10, 2026                                      │
│  • Processed: March 7, 2026 at 2:34 PM                           │
│                                                                  │
│  Line Items:                                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Item         │ Quantity │ Unit Price │ Total     │ Stock   │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ WidgetA      │ 10       │ $150       │ $1,500    │ ✅ 15   │ │
│  │ WidgetB      │ 5        │ $390       │ $1,950    │ ✅ 10   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ✅ Validation Results:                                          │
│  • All items found in inventory                                 │
│  • Sufficient stock available                                   │
│  • Amount under $10K threshold                                  │
│                                                                  │
│  ✅ Auto-Approved:                                               │
│  System automatically approved based on:                        │
│  • Clean validation (no issues)                                 │
│  • Amount below approval threshold                              │
│  • Vendor in good standing                                      │
│                                                                  │
│  💳 Payment Status: COMPLETED                                    │
│  Transaction ID: PAY-2026-03-07-1234                            │
│  Paid on: March 7, 2026 at 2:34 PM                              │
│                                                                  │
│  [📄 View Original PDF]  [📧 Email Receipt]  [🖨️ Print]         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Rejected Invoice
```
┌──────────────────────────────────────────────────────────────────┐
│  ❌ INV-1003 - Rejected                                [✕ Close]│
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Invoice Details:                                                │
│  • Vendor: Sketchy Vendor LLC                                    │
│  • Amount: $50,000.00                                            │
│  • Due Date: March 8, 2026                                       │
│  • Processed: March 7, 2026 at 1:15 PM                           │
│                                                                  │
│  ❌ Rejection Reasons:                                           │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Critical Issues (3):                                       │ │
│  │                                                            │ │
│  │ 🚫 FakeItem requested (100 units)                          │ │
│  │    Issue: Item has 0 stock in inventory                    │ │
│  │    Flagged as potentially fraudulent                       │ │
│  │                                                            │ │
│  │ 💰 Amount exceeds $10K threshold ($50,000)                 │ │
│  │    Requires executive approval                             │ │
│  │                                                            │ │
│  │ ⚠️ Vendor not in approved vendor list                      │ │
│  │    First-time vendor requires verification                 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  🤖 Agent Decision Log:                                          │
│  "Validation agent detected critical inventory mismatch.        │
│   Approval agent flagged high-risk characteristics: large       │
│   amount, unknown vendor, suspicious item. Recommend manual     │
│   verification before processing."                              │
│                                                                  │
│  Next Steps:                                                     │
│  [📧 Notify Vendor]  [🔄 Request Corrected Invoice]             │
│  [🚫 Add to Blocklist]  [📝 Manual Override]                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Screen 5: Batch Upload Progress

```
┌──────────────────────────────────────────────────────────────────┐
│  Batch Processing (15 files)                          [✕ Close] │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Overall Progress: 8/15 completed (53%)                          │
│  ████████████░░░░░░░░░░░░░░                                      │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ File                 │ Status            │ Result          │ │
│  ├────────────────────────────────────────────────────────────┤ │
│  │ invoice_1001.pdf     │ ✅ Completed       │ Auto-Approved   │ │
│  │ invoice_1002.pdf     │ ✅ Completed       │ Needs Approval  │ │
│  │ invoice_1003.txt     │ ✅ Completed       │ Rejected        │ │
│  │ invoice_1004.pdf     │ 🔄 Processing...   │ Stage 2/4       │ │
│  │ invoice_1005.json    │ ⏸️ Queued          │ Waiting...      │ │
│  │ invoice_1006.csv     │ ⏸️ Queued          │ Waiting...      │ │
│  │ ...10 more files                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  [Pause Batch]  [Cancel Remaining]  [View Summary Report]       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Progress Bar:**
- Height: 8px
- Background: #e5e7eb
- Fill: #2563eb (animated gradient for active processing)
- Rounded corners

---

## Component Library

### Buttons

**Primary Button:**
- Background: #2563eb
- Text: White, 14px, medium weight
- Padding: 10px 20px
- Rounded: 6px
- Hover: #1d4ed8
- Active: #1e40af

**Secondary Button:**
- Border: 1px solid #d1d5db
- Background: White
- Text: #374151, 14px, medium weight
- Padding: 10px 20px
- Rounded: 6px
- Hover: #f3f4f6 background

**Success Button:**
- Background: #10b981
- Text: White
- Hover: #059669

**Danger Button:**
- Background: #ef4444
- Text: White
- Hover: #dc2626

---

### Status Badges

**Badge Base:**
- Padding: 4px 12px
- Rounded: 12px (pill shape)
- Font: 12px, medium weight
- Display: inline-flex with icon + text

**Status Variants:**
- Processing: #8b5cf6 bg, #f5f3ff text
- Needs Approval: #f59e0b bg, #fffbeb text
- Approved: #10b981 bg, #d1fae5 text
- Rejected: #ef4444 bg, #fee2e2 text
- Waiting: #6b7280 bg, #f3f4f6 text
- Duplicate: #f97316 bg, #ffedd5 text (orange)
- Revision: #3b82f6 bg, #dbeafe text (blue)

---

### Icons
Use Lucide React icons:
- Upload: `<Upload />`
- Processing: `<Loader2 className="animate-spin" />`
- Success: `<CheckCircle2 />`
- Warning: `<AlertTriangle />`
- Error: `<XCircle />`
- Document: `<FileText />`
- Folder: `<Folder />`
- Search: `<Search />`
- Settings: `<Settings />`
- Close: `<X />`

---

## Responsive Behavior

### Desktop (>1024px)
- Full layout as shown
- Table displays all columns
- Modals at 800px max-width, centered

### Tablet (768px - 1024px)
- Stats in 2×2 grid instead of 1×4
- Table shows ID, Vendor, Amount, Status (hide Due Date)
- Modals at 90% width

### Mobile (<768px)
- Stats in 2×2 grid
- Table becomes card list:
  ```
  ┌─────────────────────────┐
  │ INV-1008               │
  │ SuperTech Inc.         │
  │ $15,240                │
  │ ⚠️ Needs Approval      │
  │ [View Details]         │
  └─────────────────────────┘
  ```
- Upload section full-width
- Modals full-screen

---

## Interactions & States

### Upload Zone
- **Default**: Dashed border, neutral background
- **Hover**: Blue border, light blue background
- **Drag Active**: Solid blue border, blue background
- **Uploading**: Progress bar overlay with percentage
- **Success**: Green checkmark flash, then item appears in table
- **Error**: Red shake animation, error message below

### Table Rows
- **Hover**: Entire row highlights
- **Click**: Opens detail modal
- **Loading**: Skeleton animation for new rows

### Modal Transitions
- **Open**: Fade in with slight scale up (0.95 → 1.0)
- **Close**: Fade out with slight scale down
- Duration: 200ms ease-out

### Live Updates
- **WebSocket Connection**: Updates automatically
- **New Status**: Badge color transition animation
- **Processing Stage**: Progress bar animation + pulse

---

## Error States

### Upload Errors
```
┌──────────────────────────────────────────┐
│ ❌ Upload Failed                         │
│ invoice_corrupt.pdf could not be parsed  │
│ Error: Invalid PDF format                │
│ [Try Again] [Skip]                       │
└──────────────────────────────────────────┘
```

### Duplicate Detection
```
┌────────────────────────────────────────────────────────────────┐
│ ⚠️ Duplicate Invoice Detected                                  │
├────────────────────────────────────────────────────────────────┤
│ invoice_1008.pdf appears to match an existing invoice:         │
│                                                                │
│ Original Invoice:                                              │
│ • ID: INV-1008                                                 │
│ • Vendor: SuperTech Inc.                                       │
│ • Amount: $15,240.00                                           │
│ • Status: ✅ Approved & Paid (Mar 5, 2026)                     │
│ • Due Date: March 15, 2026                                     │
│                                                                │
│ New Upload:                                                    │
│ • Vendor: SuperTech Inc.                                       │
│ • Amount: $15,240.00                                           │
│ • Due Date: March 15, 2026                                     │
│                                                                │
│ Match Confidence: 98% (vendor, amount, date match)             │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐  │
│ │ This invoice has already been processed and paid.        │  │
│ │                                                          │  │
│ │ Actions:                                                 │  │
│ │ [Skip Upload]  [View Original]  [Process as Revision]   │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Revision Detection
```
┌────────────────────────────────────────────────────────────────┐
│ 🔄 Invoice Revision Detected                                   │
├────────────────────────────────────────────────────────────────┤
│ invoice_1008_rev1.pdf appears to be a revision:                │
│                                                                │
│ Original (INV-1008):                                           │
│ • Amount: $15,240.00                                           │
│ • Items: 2× SuperGizmo, 3× MegaSprocket                       │
│ • Status: ⏸️ Pending Approval                                  │
│                                                                │
│ New Upload (Revision 1):                                       │
│ • Amount: $16,500.00  ⚠️ Changed                               │
│ • Items: 2× SuperGizmo, 4× MegaSprocket  ⚠️ Changed            │
│ • Contains "REVISED" or "REV 1" in filename                    │
│                                                                │
│ Differences Detected:                                          │
│ • Amount increased by $1,260.00                                │
│ • MegaSprocket quantity: 3 → 4                                 │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐  │
│ │ Process this as:                                         │  │
│ │                                                          │  │
│ │ [⭕ Replace Original] - Cancel INV-1008, process new     │  │
│ │ [➕ Process as New] - Create INV-1008-R1                 │  │
│ │ [❌ Reject Upload] - Keep original, discard revision    │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Network Errors
```
┌──────────────────────────────────────────┐
│ ⚠️ Connection Lost                       │
│ Reconnecting...                          │
│ [Retry Now] [Work Offline]               │
└──────────────────────────────────────────┘
```

### Processing Errors
```
┌──────────────────────────────────────────┐
│ ❌ Stage 2: Validation Failed            │
│ Database connection timeout              │
│ The system will retry automatically      │
│ [Retry Now] [Cancel] [View Logs]         │
└──────────────────────────────────────────┘
```

---

## Data Flow & API Integration

The UI should connect to these backend endpoints:

### POST /api/upload
- Upload single invoice
- Returns: `{ invoice_id, status: "processing" }`

### POST /api/upload/batch
- Upload multiple invoices
- Returns: `{ batch_id, total_files, status: "queued" }`

### GET /api/invoices
- List all invoices with filters
- Query params: `status`, `date_range`, `vendor`
- Returns: Array of invoice objects

### GET /api/invoices/:id
- Get single invoice details
- Returns: Full invoice object with all stage data

### WebSocket /ws/processing
- Real-time updates for invoice processing
- Events: `stage_started`, `stage_completed`, `status_changed`

### POST /api/approve/:id
- VP approves invoice
- Returns: Updated invoice with payment status

### POST /api/reject/:id
- VP rejects invoice
- Body: `{ reason: string }`
- Returns: Updated invoice

### POST /api/duplicate/resolve/:id
- Resolve duplicate detection
- Body: `{ action: "skip" | "process_anyway" | "view_original" }`
- Returns: Action result

### POST /api/revision/resolve/:id
- Resolve revision detection
- Body: `{ action: "replace_original" | "process_as_new" | "reject" }`
- Returns: Updated invoice(s)

---

## Sample Data Structure

```json
{
  "invoice_id": "INV-1008",
  "vendor": "SuperTech Inc.",
  "amount": 15240.00,
  "due_date": "2026-03-15",
  "status": "needs_approval",
  "uploaded_at": "2026-03-07T14:22:00Z",
  "is_duplicate": false,
  "duplicate_of": null,
  "is_revision": false,
  "revision_number": 0,
  "original_invoice_id": null,
  "stages": {
    "ingestion": {
      "status": "completed",
      "duration_ms": 800,
      "extracted_data": {
        "vendor": "SuperTech Inc.",
        "amount": 15240.00,
        "items": [
          { "name": "SuperGizmo", "quantity": 2, "unit_price": 5000 },
          { "name": "MegaSprocket", "quantity": 3, "unit_price": 1746.67 }
        ],
        "due_date": "2026-03-15"
      }
    },
    "validation": {
      "status": "completed",
      "duration_ms": 1200,
      "issues": [
        { "type": "unknown_item", "item": "SuperGizmo", "severity": "warning" },
        { "type": "unknown_item", "item": "MegaSprocket", "severity": "warning" }
      ],
      "duplicate_check": {
        "is_duplicate": false,
        "match_confidence": 0,
        "matched_invoice_id": null,
        "differences": []
      }
    },
    "approval": {
      "status": "pending",
      "reasoning": "Invoice exceeds $10,000 threshold and references items not currently in our inventory system. Manual review recommended to verify vendor legitimacy and item codes."
    },
    "payment": {
      "status": "waiting"
    }
  }
}
```

### Duplicate Invoice Example
```json
{
  "invoice_id": "DUPLICATE-DETECTED",
  "vendor": "SuperTech Inc.",
  "amount": 15240.00,
  "due_date": "2026-03-15",
  "status": "duplicate_detected",
  "uploaded_at": "2026-03-07T15:30:00Z",
  "is_duplicate": true,
  "duplicate_of": "INV-1008",
  "duplicate_match_confidence": 98,
  "original_invoice_status": "approved_and_paid",
  "stages": {
    "ingestion": {
      "status": "completed",
      "duration_ms": 750,
      "extracted_data": {
        "vendor": "SuperTech Inc.",
        "amount": 15240.00,
        "items": [
          { "name": "SuperGizmo", "quantity": 2 },
          { "name": "MegaSprocket", "quantity": 3 }
        ],
        "due_date": "2026-03-15"
      }
    },
    "validation": {
      "status": "completed",
      "duration_ms": 600,
      "duplicate_check": {
        "is_duplicate": true,
        "match_confidence": 98,
        "matched_invoice_id": "INV-1008",
        "matching_fields": ["vendor", "amount", "due_date", "items"],
        "differences": []
      }
    }
  }
}
```

### Revision Invoice Example
```json
{
  "invoice_id": "INV-1008-R1",
  "vendor": "SuperTech Inc.",
  "amount": 16500.00,
  "due_date": "2026-03-15",
  "status": "revision_detected",
  "uploaded_at": "2026-03-07T16:00:00Z",
  "is_duplicate": false,
  "is_revision": true,
  "revision_number": 1,
  "original_invoice_id": "INV-1008",
  "original_invoice_status": "pending_approval",
  "stages": {
    "ingestion": {
      "status": "completed",
      "duration_ms": 820,
      "extracted_data": {
        "vendor": "SuperTech Inc.",
        "amount": 16500.00,
        "items": [
          { "name": "SuperGizmo", "quantity": 2 },
          { "name": "MegaSprocket", "quantity": 4 }
        ],
        "due_date": "2026-03-15",
        "revision_indicators": ["filename contains 'rev1'", "document marked as revised"]
      }
    },
    "validation": {
      "status": "completed",
      "duration_ms": 900,
      "duplicate_check": {
        "is_duplicate": false,
        "is_revision": true,
        "match_confidence": 85,
        "matched_invoice_id": "INV-1008",
        "matching_fields": ["vendor", "due_date"],
        "differences": [
          {
            "field": "amount",
            "original": 15240.00,
            "revised": 16500.00,
            "change": "+$1,260.00"
          },
          {
            "field": "items.MegaSprocket.quantity",
            "original": 3,
            "revised": 4,
            "change": "+1 unit"
          }
        ]
      }
    }
  }
}
```

---

## Implementation Notes

### Tech Stack
- **Frontend**: React 18+ with TypeScript
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **State**: React Query for server state, Zustand for UI state
- **Real-time**: Socket.io-client or native WebSocket
- **File Upload**: react-dropzone
- **Tables**: TanStack Table (React Table v8)
- **Modals**: Headless UI or Radix UI
- **Forms**: React Hook Form + Zod validation

### Accessibility
- All interactive elements keyboard navigable
- Proper ARIA labels on all buttons and inputs
- Status updates announced to screen readers
- Color is not the only indicator (icons + text)
- Focus visible on all interactive elements

### Performance
- Lazy load modals
- Virtualize long invoice lists (react-virtual)
- Debounce search inputs
- Optimistic UI updates for actions
- Cache invoice details client-side

---

## Success Metrics

The UI should optimize for:
1. **Time to upload**: <5 seconds from drop to processing start
2. **Visibility**: All 4 stages visible within one screen (no scrolling)
3. **Decision speed**: VP can approve/reject in <30 seconds
4. **Error recovery**: Clear next steps for every error state
5. **Batch efficiency**: Process 50 invoices with <1 minute setup

---

## Final Deliverable Checklist

When implementing this spec, ensure:
- ✅ All 5 main screens implemented
- ✅ Real-time WebSocket updates working
- ✅ Drag-and-drop upload functional
- ✅ Batch upload with progress tracking
- ✅ Approval queue with full reasoning display
- ✅ Error states for all failure modes
- ✅ Responsive design (desktop + tablet + mobile)
- ✅ Accessibility compliance
- ✅ Loading states for all async operations
- ✅ PDF viewer integration (for "View Original PDF")

---

This specification is ready to hand to Claude Code for full implementation.
