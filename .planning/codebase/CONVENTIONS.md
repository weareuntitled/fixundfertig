<!-- refreshed: 2026-05-05 -->
# Coding Conventions

**Analysis Date:** 2026-05-05

## Naming Patterns

**Files:**
- Python modules: `lowercase_underscore.py` (e.g., `auth_guard.py`, `invoice_calculations.py`)
- Page modules: `page_name.py` (e.g., `invoices.py`, `customers.py`)
- Service modules: `service_name.py` (e.g., `auth.py`, `storage.py`)

**Functions:**
- Page renderers: `render_page_name()` (e.g., `render_invoices()`, `render_customers()`)
- Service functions: `verb_noun()` pattern (e.g., `get_user()`, `create_invoice()`, `validate_document_upload()`)
- Private functions: `_private_function()` with leading underscore

**Variables:**
- snake_case: `user_id`, `company_name`, `invoice_total`
- Private variables: `_internal_state`

**Types:**
- SQLModel classes: `PascalCase` (e.g., `User`, `Invoice`, `Company`)
- Pydantic models: `PascalCase` (e.g., `N8NIngestPayload`, `N8NExtractedPayload`)
- Enums: `PascalCase` with `UpperCase` values (e.g., `InvoiceStatus.DRAFT`)

## Code Style

**Formatting:**
- No explicit formatter configured (not in pyproject.toml)
- Follows standard Python conventions (PEP 8 implicit)

**Linting:**
- ruff available as optional lint dependency (`pyproject.toml:lint`)
- mypy available as optional typecheck dependency (`pyproject.toml:typecheck`)

## Import Organization

**Order:**
1. Standard library (os, sys, datetime, etc.)
2. Third-party packages (fastapi, nicegui, sqlmodel)
3. Local application imports (from app.*)

**Pattern observed:**
```python
import os
import json
from datetime import datetime

from fastapi import HTTPException
from nicegui import ui, app
from sqlmodel import select

from app.data import Company, Customer
from app.services.auth import require_auth
from app.pages._shared import get_current_user_id
```

**Path Aliases:**
- No explicit path aliases configured (absolute imports from app.*)

## Error Handling

**Patterns:**
- FastAPI: `raise HTTPException(status_code=XXX, detail="message")`
- Service layer: Return None or raise exception
- UI: Display errors via NiceGUI notifications (`ui.notify()`)

## Logging

**Framework:** Python standard `logging` module

**Patterns:**
- Use `logging.getLogger(__name__)` for module-level loggers
- Log levels: `logger.info()`, `logger.warning()`, `logger.exception()`
- Configuration in `app/logging_setup.py`

## Comments

**When to Comment:**
- Complex business logic
- Non-obvious workarounds
- TODO/FIXME markers for technical debt

**JSDoc/TSDoc:**
- Not applicable (Python code only)

## Function Design

**Size:** Varies; some functions are lengthy (e.g., `app/main.py` endpoints)

**Parameters:**
- Use type hints for clarity
- Default values where appropriate

**Return Values:**
- Pydantic models for API endpoints
- SQLModel objects for database queries
- Dicts for serialized responses

## Module Design

**Exports:**
- Not using explicit `__all__` exports
- Import full module paths

**Barrel Files:**
- Not detected (no extensive use of `__init__.py` for re-exports)

---

*Convention analysis: 2026-05-05*