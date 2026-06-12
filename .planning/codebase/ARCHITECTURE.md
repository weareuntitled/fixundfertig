<!-- refreshed: 2026-05-05 -->
# Architecture

**Analysis Date:** 2026-05-05

## System Overview

FixundFertig is a German invoicing and ERP SaaS platform built with Python, NiceGUI, and FastAPI. It provides a complete invoice management system with document ingestion, customer management, PDF generation, and webhook integrations.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Client (Browser)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Caddy (TLS Reverse Proxy)                          │
│                    Port 80/443 → Internal Services                         │
└─────────────────────────────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────────┐   ┌─────────────────────┐
│   FixundFertig App  │   │        n8n           │
│   (NiceGUI+FastAPI) │   │  (Automation)       │
│     Port 8080       │   │    Port 5678        │
└─────────────────────┘   └─────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Data Layer                                          │
├─────────────────────┬─────────────────────┬───────────────────────────────┤
│   SQLite (Default)  │   Local Storage      │        Redis (Cache)          │
│  storage/database.db│  storage/invoices/   │    (Optional, via REDIS_URL)  │
└─────────────────────┴─────────────────────┴───────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `app/main.py` | FastAPI application entry, routing, middleware, API endpoints | `app/main.py` |
| `app/data.py` | SQLAlchemy/SQLModel database models and schema | `app/data.py` |
| `app/pages/*` | NiceGUI UI page renderers for each feature | `app/pages/*.py` |
| `app/services/*` | Business logic layer (auth, storage, invoices, email) | `app/services/*.py` |
| `app/renderer.py` | PDF generation using ReportLab/fpdf2 | `app/renderer.py` |
| `app/integrations/n8n_client.py` | n8n webhook client | `app/integrations/n8n_client.py` |

## Pattern Overview

**Overall:** Monolithic Python web application with NiceGUI frontend and FastAPI backend sharing the same codebase.

**Key Characteristics:**
- Single Python process handles both UI (NiceGUI) and REST API (FastAPI)
- SQLite database by default; schema defined via SQLModel
- Session-based authentication with server-side sessions
- File-based storage for uploaded documents and generated PDFs
- n8n integration for document processing automation

## Layers

**Frontend Layer (NiceGUI):**
- Location: `app/pages/*.py`
- Contains: UI page renderers using NiceGUI components
- Depends on: `app/ui_components.py`, `app/ui_theme.py`, `app/styles.py`
- Used by: Browser client via NiceGUI's WebSocket connection

**API Layer (FastAPI):**
- Location: `app/main.py`
- Contains: REST endpoints under `/api/*` and `/api/webhooks/*`
- Depends on: Services, data models
- Used by: Browser AJAX, n8n webhooks, external integrations

**Service Layer:**
- Location: `app/services/`
- Contains: Business logic (auth, document processing, PDF generation)
- Depends on: Data models
- Used by: API layer, pages

**Data Layer:**
- Location: `app/data.py`, `app/models/`
- Contains: SQLModel entities and database operations
- Depends on: SQLAlchemy
- Used by: Service layer

## Data Flow

### Primary Request Path (Browser → UI)

1. **Entry:** Browser connects to NiceGUI WebSocket (`app/main.py:519`)
2. **Auth Check:** `auth_guard.py` validates session
3. **Page Render:** `pages/*.py` render UI using NiceGUI components
4. **Data Load:** Pages call service functions to fetch data from SQLite

### API Request Path (External → REST)

1. **Entry:** FastAPI route in `app/main.py` (e.g., `/api/documents`, `/api/webhooks/n8n/ingest`)
2. **Validation:** Pydantic models validate request payload
3. **Auth Check:** Session or HMAC signature verification
4. **Service Call:** Business logic executed via service modules
5. **Response:** JSON response returned

### Document Upload Flow (n8n → Storage)

1. **Webhook:** `app/main.py:660` (`/api/webhooks/n8n/ingest`)
2. **Validation:** HMAC signature verification, timestamp validation
3. **File Processing:** Base64 decoded, validated for file type
4. **Storage:** Local filesystem (`storage/documents/`) or blob storage
5. **Database:** Document record created in SQLite

### Invoice PDF Generation

1. **Request:** API call to `/api/invoices/{id}/pdf` or page request
2. **Cache Check:** TTLCache checks for cached PDF (`app/main.py:87-95`)
3. **Generation:** `renderer.py:render_invoice_to_pdf_bytes()` uses ReportLab/fpdf2
4. **Cache Store:** Generated PDF cached for 5 minutes
5. **Response:** FileResponse or JSON with PDF bytes

## Key Abstractions

**Database Session Abstraction:**
- Purpose: Manage database connections across async contexts
- Examples: `app/data.py:get_session()` context manager
- Pattern: SQLModel Session with contextmanager

**Service Interface Pattern:**
- Purpose: Encapsulate business logic
- Examples: `app/services/invoices.py`, `app/services/auth.py`
- Pattern: Module-level functions returning data or performing actions

**Storage Abstraction:**
- Purpose: Abstract file storage (local vs blob)
- Examples: `app/services/storage.py:blob_storage()`
- Pattern: Factory returning storage backend based on configuration

**Authentication Guard:**
- Purpose: Centralized auth validation
- Examples: `app/auth_guard.py:require_auth()`, `is_authenticated()`
- Pattern: Decorator and function-based guards checking session state

## Entry Points

**Application Entry:**
- Location: `app/main.py`
- Triggers: `python app/main.py` or Docker `python main.py`
- Responsibilities: NiceGUI app initialization, FastAPI app mounting, middleware setup, static file serving

**Development Entry:**
- Location: `app/run_dev.py`
- Triggers: Development server startup
- Responsibilities: Development-specific configuration

**Webhook Entry:**
- Location: `app/main.py:660` (`/api/webhooks/n8n/ingest`)
- Triggers: n8n automation sends document to app
- Responsibilities: Validate webhook signature, process document upload

## Architectural Constraints

- **Threading:** Single-threaded event loop via uvicorn (async) + NiceGUI's synchronous UI handlers
- **Global state:** NiceGUI's `app.storage.user` for per-user session state; SQLite connection pool
- **Circular imports:** Avoided via lazy imports in `app/main.py`
- **No multi-tenancy isolation:** Single database with company_id foreign keys

## Anti-Patterns

### Mixed API and UI in Same File

**What happens:** `app/main.py` contains both FastAPI routes AND NiceGUI page handlers
**Why it's wrong:** Hard to separate concerns, large file (~2000+ lines), unclear separation of API vs UI responsibilities
**Do this instead:** Keep API routes in `app/main.py` but extract page handlers to `app/pages/` (already done), consider splitting `main.py` into `api.py` and `app.py`

### Environment Variable Loading Timing

**What happens:** `load_env()` called in multiple places (`app/main.py`, `app/data.py`, `app/env.py`)
**Why it's wrong:** Potential for race conditions, unclear initialization order
**Do this instead:** Single entry point for env loading before any other imports

### Inline SQL Queries

**What happens:** Direct SQLModel `session.exec(select(...))` calls throughout `main.py` and services
**Why it's wrong:** Business logic mixed with data access, harder to test
**Do this instead:** Use repository pattern with dedicated data access methods in `app/services/`

## Error Handling

**Strategy:** Return HTTP exceptions with structured error messages; UI displays errors via NiceGUI notifications

**Patterns:**
- `HTTPException(status_code=XXX, detail="message")` - FastAPI errors
- `try/except` blocks with logging in `main.py` endpoints
- `session.rollback()` on database errors

## Cross-Cutting Concerns

**Logging:** Structured logging via `logging_setup.py`, log levels configured per environment
**Validation:** Pydantic models for API request validation (e.g., `N8NIngestPayload`)
**Authentication:** Session-based with HMAC-signed cookies; owner bootstrap via environment variables

---

*Architecture analysis: 2026-05-05*