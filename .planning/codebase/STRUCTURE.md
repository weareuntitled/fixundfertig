<!-- refreshed: 2026-05-05 -->
# Codebase Structure

**Analysis Date:** 2026-05-05

## Directory Layout

```
fixundfertig/
├── app/                    # Main application code
│   ├── __init__.py
│   ├── main.py             # FastAPI + NiceGUI app entry point
│   ├── data.py             # SQLModel database models
│   ├── env.py              # Environment variable loader
│   ├── logic.py            # Core business logic functions
│   ├── actions.py          # Action handlers
│   ├── renderer.py         # PDF generation
│   ├── renderer_interface.py
│   ├── auth_guard.py       # Authentication middleware
│   ├── styles.py           # UI styling constants
│   ├── ui_theme.py         # Theme configuration
│   ├── ui_components.py    # Reusable UI components
│   ├── invoice_numbering.py
│   ├── invoice_calculations.py
│   ├── invoice_customer_merge.py
│   ├── logging_setup.py
│   ├── pages/              # NiceGUI page handlers
│   │   ├── __init__.py
│   │   ├── _shared.py      # Shared page utilities
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── customers.py
│   │   ├── customer_new.py
│   │   ├── customer_detail.py
│   │   ├── invoices.py
│   │   ├── invoice_create.py
│   │   ├── invoice_detail.py
│   │   ├── invoice_utils.py
│   │   ├── expenses.py
│   │   ├── documents.py
│   │   ├── settings.py
│   │   ├── invites.py
│   │   ├── ledger.py
│   │   └── exports.py
│   ├── services/           # Business logic services
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── account.py
│   │   ├── companies.py
│   │   ├── storage.py
│   │   ├── invoices.py
│   │   ├── invoice_pdf.py
│   │   ├── email.py
│   │   ├── documents.py
│   │   ├── documents_ingest.py
│   │   ├── iban.py
│   │   └── blob_storage.py
│   ├── models/             # Additional data models
│   │   ├── __init__.py
│   │   └── document.py
│   ├── components/          # UI components
│   │   ├── __init__.py
│   │   └── invoice_pdf_preview.py
│   ├── integrations/       # External integrations
│   │   ├── __init__.py
│   │   └── n8n_client.py
│   └── static/             # Static assets
├── tests/                  # Test files
│   ├── conftest.py
│   └── test_*.py
├── storage/               # Local file storage
│   ├── database.db        # SQLite database
│   ├── invoices/          # Generated PDFs
│   └── documents/         # Uploaded documents
├── backups/              # Backup files
├── docs/                 # Documentation
├── .github/workflows/    # GitHub Actions CI/CD
├── Dockerfile             # Docker image build
├── docker-compose.yml    # Development compose
├── docker-compose.prod.yml  # Production compose
├── Caddyfile             # Caddy reverse proxy config
├── pyproject.toml         # Python project config
├── requirements.txt       # Python dependencies
└── .env.example           # Environment template
```

## Directory Purposes

**app/:**
- Purpose: Main application code - the only runtime code base
- Contains: All Python modules for the application
- Key files: `main.py`, `data.py`, `pages/`, `services/`

**app/pages/:**
- Purpose: NiceGUI page handlers for each UI screen
- Contains: Render functions for dashboard, customers, invoices, documents, etc.
- Key files: `_shared.py` (shared utilities), individual page modules

**app/services/:**
- Purpose: Business logic layer - service modules
- Contains: Auth, storage, invoices, email, documents, blob storage
- Key files: `auth.py`, `invoices.py`, `documents.py`

**app/models/:**
- Purpose: Additional data models beyond core data.py
- Contains: Document-related models
- Key files: `document.py`

**app/components/:**
- Purpose: Reusable UI components
- Contains: Invoice PDF preview component
- Key files: `invoice_pdf_preview.py`

**app/integrations/:**
- Purpose: External service integrations
- Contains: n8n webhook client
- Key files: `n8n_client.py`

**storage/:**
- Purpose: Local file storage for application data
- Contains: SQLite database, invoices, documents
- Generated: Yes
- Committed: No (in .gitignore)

**tests/:**
- Purpose: Test suite using pytest
- Contains: Test modules and fixtures
- Key files: `conftest.py`

## Key File Locations

**Entry Points:**
- `app/main.py`: Application entry, FastAPI + NiceGUI app
- `app/run_dev.py`: Development server entry

**Configuration:**
- `pyproject.toml`: Python project metadata and dependencies
- `.env.example`: Environment variable template

**Core Logic:**
- `app/data.py`: Database models and session management
- `app/logic.py`: Core business logic
- `app/services/`: Service layer modules

**Testing:**
- `tests/`: Test directory with pytest configuration
- `conftest.py`: pytest fixtures

## Naming Conventions

**Files:**
- Python modules: `lowercase_underscore.py`
- Page handlers: `page_name.py` (e.g., `invoices.py`, `dashboard.py`)
- Services: `service_name.py` (e.g., `auth.py`, `storage.py`)

**Functions:**
- Page renderers: `render_page_name()` (e.g., `render_invoices()`)
- Service functions: `verb_noun()` (e.g., `get_user()`, `create_invoice()`)

**Database Models:**
- SQLModel classes: `PascalCase` (e.g., `User`, `Invoice`, `Company`)

## Where to Add New Code

**New Feature (UI + Backend):**
- UI: Add new file in `app/pages/` with `render_*` function
- Backend: Add API endpoint in `app/main.py` or new service in `app/services/`
- Tests: Add test file in `tests/`

**New API Endpoint:**
- Add route to `app/main.py` using `@app.get/post/put/delete`
- Use Pydantic model for request validation

**New Service:**
- Create new module in `app/services/`
- Follow existing service patterns (module-level functions)

**New Database Model:**
- Add SQLModel class to `app/data.py`
- Use Field() for column definitions
- Add relationships using Relationship()

**Utilities:**
- Shared helpers: Add to appropriate service module or create new service
- UI helpers: Add to `app/ui_components.py` or `app/pages/_shared.py`

## Special Directories

**storage/:**
- Purpose: Local SQLite database and file storage
- Generated: Yes (by application at runtime)
- Committed: No (in .gitignore)

**backups/:**
- Purpose: Database backup storage
- Generated: Yes (by backup container)
- Committed: Yes (archived backups)

**venv/:**
- Purpose: Python virtual environment
- Generated: Yes (by `python -m venv venv`)
- Committed: No (in .gitignore)

**__pycache__/:**
- Purpose: Python bytecode cache
- Generated: Yes (by Python interpreter)
- Committed: No (in .gitignore)

---

*Structure analysis: 2026-05-05*