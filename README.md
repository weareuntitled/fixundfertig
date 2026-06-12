# FixundFertig — Technical Documentation

> Senior architecture & codebase reference for the FixundFertig NiceGUI + FastAPI SaaS invoicing & ERP platform.

---

## Architekturregeln

1. **Lean bleiben:** Kleine, lokale Änderungen statt Refactors.
2. **Ende-zu-Ende:** Jede Änderung muss über die GUI bedienbar und im laufenden UI verifizierbar sein.
3. **Kein toter Code:** Keine UI ohne Backend-Pfad, kein Backend ohne UI-Einstieg.
4. **Material-lean UI:** Minimal, clean, vorhandene Styles/Komponenten nutzen.
5. **NiceGUI sanitize:** `ui.html(..., sanitize=True/False)` immer explizit setzen.
6. **Standard NiceGUI Patterns:** `ui.refreshable`/einfaches State-Update bevorzugen.
7. **Testbarkeit:** GUI-Hook/Statusanzeige für manuelle Tests, wenn nötig.
8. **Keine Über-Architektur:** Keine neuen Systeme ohne echten Bedarf.
9. **Sicherheit:** Fehler klar im UI anzeigen, keine sensiblen Leaks, geschützte Ressourcen prüfen.

---

## Startanleitung (lokal)

### Installation

Mit `uv`:
```bash
uv pip install -r requirements.txt
```

Mit `pip`:
```bash
pip install -r requirements.txt
```

### Starten

```bash
python app/main.py
```

Optional: im Repo-Root ausführen (damit `app/` als Script-Verzeichnis gilt).

### Frontend (React) — M1 aktiv

Das React-Frontend befindet sich in `frontend/` (Vite + TypeScript + TanStack Router/Query). Es läuft parallel zum NiceGUI-Backend.

```bash
# Terminal 1: Backend (Port 8080)
python app/main.py

# Terminal 2: Frontend Dev-Server (Port 5173)
cd frontend
npm install     # einmalig
npm run dev
# → http://localhost:5173 — Login-Seite
```

Auth-Flow: `POST /api/auth/login` setzt `ff_session` (httpOnly) + `ff_csrf` Cookies; React sendet bei mutating Calls `X-CSRF-Token`-Header. Vite-Proxy leitet `/api` an Backend weiter — kein CORS-Setup nötig.

Smoke-Tests:
```bash
cd frontend
npm run build       # tsc + vite build, muss grün sein
npm run test        # Vitest (1 Smoke-Test)
npm run test:e2e    # Playwright (1 Smoke-Test gegen Login-Seite)
```

Detaillierter Plan: siehe [`docs/react_handoff.md`](docs/react_handoff.md) (insb. §4 Tag-1-Runbook, §5 Phase-Plan M0–M6).

### Code-Struktur

- **`app/` ist die einzige Codebasis und der Runtime-Entry-Point.** Docker startet `python main.py` im Container, nachdem der Inhalt von `app/` nach `/app` kopiert wurde. Daher läuft die produktive App immer über `app/main.py`.【F:Dockerfile†L21-L32】

## 🧭 System Architecture

### High-level flow (runtime)

```
[Browser]
   │
   ▼
[Caddy (TLS + reverse proxy)]
   ├─▶ / -> FixundFertig App (NiceGUI + FastAPI)
   └─▶ / -> n8n (automation + webhooks)

FixundFertig App
   └─▶ SQLite storage (storage/database.db + storage/invoices)

n8n
   └─▶ Local filesystem volume (/home/node/.n8n)
```

**Reality check:** The production Docker Compose in this repo defines **three services (app, n8n, caddy)** and **does not provision Postgres or Redis**. The application itself uses SQLite by default (`storage/database.db`), and n8n stores its data in its own volume. If Postgres/Redis are desired, they must be added externally (not in this repo).【F:docker-compose.prod.yml†L1-L50】【F:data.py†L174-L181】

### Service breakdown (current Docker Compose)

| Service | Role | Internal Port | External Port | Volumes | Key configuration |
| --- | --- | --- | --- | --- | --- |
| `app` | NiceGUI + FastAPI app | 8080 | 8080 (dev) | `./app:/app` (dev) / `app_storage:/app/storage` (prod) | Uses `APP_BASE_URL` and `STORAGE_SECRET` in prod for URL generation and session signing.【F:docker-compose.yml†L1-L13】【F:docker-compose.prod.yml†L1-L14】 |
| `n8n` | Automation & webhook orchestrator | 5678 | 5678 | `n8n_data:/home/node/.n8n` | Execution pruning, filesystem binary mode; TLS termination expected at Caddy in prod.【F:docker-compose.yml†L15-L28】【F:docker-compose.prod.yml†L15-L30】 |
| `caddy` (prod only) | TLS + reverse proxy | 80/443 | 80/443 | `./Caddyfile` + Caddy data/config volumes | Routes `APP_DOMAIN` and `N8N_DOMAIN` hostnames to app + n8n; depends on both services.【F:docker-compose.prod.yml†L32-L48】【F:Caddyfile†L1-L6】 |

**Service dependencies & isolation:**
- `caddy` depends on `app` and `n8n` (`depends_on`) so it only starts after upstreams are up.【F:docker-compose.prod.yml†L32-L46】
- No explicit resource limits or network isolation are configured; Docker uses the default network and resource constraints are inherited from the host.【F:docker-compose.yml†L1-L28】【F:docker-compose.prod.yml†L1-L50】

---

## 🗄️ Database Schema & Data Models

## 🔐 Invite-only Access & Owner Bootstrap

FixundFertig runs with an invite-only login/registration flow. Access is limited to:
- the **owner account** configured via environment variables, and
- email addresses explicitly added in the **Einladungen** UI by the owner.

### Required environment variables
Set these variables in your runtime environment (Docker, systemd, or `.env` if applicable):
- `OWNER_EMAIL`: the admin/owner email address (e.g. `djdanep@gmail.com`).
- `OWNER_PASSWORD`: the admin/owner password.

On startup, the app will create or update the owner account using these values and mark it
as active + email-verified for immediate login. If either variable is missing, the bootstrap
step is skipped (no owner is created).【F:app/services/auth.py†L18-L60】【F:app/main.py†L177-L188】

The app loads environment values from `.env` in the repo root (`/workspace/fixundfertig/.env`) or `app/.env` via `load_env()` before the UI starts, so placing `OWNER_EMAIL` and `OWNER_PASSWORD` there works out of the box.【F:app/env.py†L1-L33】【F:app/main.py†L177-L184】

### How invite-only access is enforced
- **Signup**: blocked unless the email is invited or matches `OWNER_EMAIL`.【F:app/services/auth.py†L64-L163】
- **Login**: blocked unless the user’s email is invited or matches `OWNER_EMAIL`.【F:app/services/auth.py†L298-L309】【F:app/pages/auth.py†L95-L120】
- **Session guard**: if a user is removed from the allowlist, active sessions are cleared and redirected to login.【F:app/auth_guard.py†L6-L13】

### Owner UI entry point
The owner sees a sidebar entry **Access → Einladungen** which provides invite management:
add/remove emails and view the active list. Non-owner users cannot access this page.【F:app/main.py†L1302-L1353】【F:app/pages/invites.py†L26-L89】

## 🧾 n8n Dokumenten-Ingest Debugging

Eine praxisnahe Debugging- und Fehlerbehandlungs-Referenz für den n8n-Ingest,
inkl. UI-Debug-Buttons und Event-Reset findet sich hier:
`docs/n8n_ingest_debugging.md`.【F:docs/n8n_ingest_debugging.md†L1-L74】

### Storage engine
- **SQLite** via SQLModel with a local file at `storage/database.db`. Tables are created automatically at startup with **schema “ensure_” functions** to add missing columns when upgrading older databases.【F:data.py†L174-L355】

### Entities (SQLModel tables)

**Core Auth**
- `User`: login identity with email/username, hashed password, activation and verification flags, and relationships to tokens/companies.【F:data.py†L23-L49】
- `Token`: time-bound email verification & password reset tokens tied to a user.【F:data.py†L51-L60】

**Organization**
- `Company`: owns invoices, customers, expenses, and configuration (invoice numbering, SMTP, n8n integration, etc.).【F:data.py†L62-L101】
- `Customer`: belongs to a company and stores billing/recipient info and status metadata.【F:data.py†L103-L128】

**Invoicing**
- `Invoice`: core invoice header with status, recipient info, and PDF storage metadata.【F:data.py†L130-L147】
- `InvoiceItem`: line items (description/quantity/unit price).【F:data.py†L162-L167】
- `InvoiceRevision`: audit snapshots for “Edit with risk” flows (revision number, reason, snapshot, PDF history).【F:data.py†L149-L160】
- `InvoiceItemTemplate`: reusable item templates per company.【F:data.py†L169-L175】

**Documents & Automation**
- `Document`: uploaded files + extracted metadata (vendor/date/amount/keywords).【F:data.py†L191-L228】
- `DocumentMeta`: raw payload, line items, and compliance flags (JSON blobs).【F:data.py†L230-L235】
- `WebhookEvent`: idempotency guard for n8n webhooks (prevents duplicates).【F:data.py†L237-L242】

**Finance & Audit**
- `Expense`: outflow records tied to a company (import or manual).【F:data.py†L177-L189】
- `AuditLog`: minimal audit trail for actions like invoice exports and expense mutations.【F:data.py†L168-L176】

### Relationships & entity flow
- `User → Company → Customer → Invoice → InvoiceItem` is the primary business chain. User ownership is enforced by `Company.user_id` and derived ownership checks in UI and API endpoints.【F:data.py†L23-L147】【F:pages/_shared.py†L44-L74】【F:main.py†L560-L654】
- Invoice revisioning is “append-only”: a finalized invoice is snapshotted into `InvoiceRevision`, then a new draft invoice is created and linked back via `related_invoice_id` for auditability.【F:pages/_shared.py†L350-L437】

### Key field definitions
- `Invoice.status`: Enum `DRAFT → OPEN → SENT → PAID` (plus `FINALIZED`, `CANCELLED`). This drives UI badges, workflow transitions, and PDF visibility logic.【F:data.py†L17-L33】【F:pages/_shared.py†L458-L496】
- `Document.storage_key`: logical key used by the storage backend (`LocalStorage` or S3) for blobs; also copied into `storage_path` for filesystem access.【F:services/documents.py†L141-L219】

---

## 📁 File-by-File Technical Reference

### Core services

#### `app/data.py`
**Purpose:** Defines SQLModel tables, database engine, schema migrations, and import helpers.

**Main functions & behavior**
- `get_session()` / `session_scope()`: DB session context managers for transaction handling with rollback on error.【F:data.py†L186-L210】
- `prevent_finalized_invoice_updates()`: SQLAlchemy event listener that prevents edits to finalized invoices (status locked unless cancelled/open/sent/paid).【F:data.py†L212-L227】
- `ensure_*_schema()` family: schema drift correction (adds missing columns or tables), enabling in-place upgrades without migrations.【F:data.py†L231-L355】
- `get_valid_token()`: validates unexpired, unused tokens by purpose for auth flows.【F:data.py†L373-L384】
- Import helpers: `load_*_import_dataframe`, `process_*_import` parse CSV/Excel and insert customer/expense/invoice rows with defensive parsing.【F:data.py†L388-L505】

**Error handling**
- Importers use broad `try/except` to skip invalid rows without breaking the full import pipeline.【F:data.py†L413-L505】

#### `app/main.py`
**Purpose:** FastAPI API endpoints, NiceGUI app wiring, PDF caching, address autocomplete, webhook ingestion, and document APIs.

**Endpoints (selected)**
- `GET /api/address-autocomplete`: proxies OpenStreetMap Nominatim and formats address suggestions.【F:main.py†L88-L147】
- `POST /api/webhooks/n8n/ingest`: HMAC-signed ingest endpoint for base64 payloads, idempotent by `event_id` + `WebhookEvent`.【F:main.py†L150-L333】
- `POST /api/webhooks/n8n/upload`: multipart upload for n8n with metadata extraction and duplicate detection (SHA-256).【F:main.py†L342-L520】
- `GET /api/invoices/{id}/pdf`: serves cached or newly rendered invoice PDF bytes, persisting files to `storage/invoices` as needed.【F:main.py†L620-L714】
- `POST /api/documents/upload`, `GET /api/documents`, `GET /api/documents/{id}/file`, `DELETE /api/documents/{id}`: document upload, query, retrieval, and deletion with auth checks.【F:main.py†L522-L706】

**UI composition**
- `layout_wrapper()` constructs the sidebar, header, and wraps page content rendering based on `app.storage.user["page"]`.【F:main.py†L717-L1100】

**Error handling**
- API endpoints use `HTTPException` for auth/validation failures and return JSON errors to clients.【F:main.py†L113-L333】【F:main.py†L342-L706】

#### `app/logic.py`
**Purpose:** Core invoice calculations, exports, and data packaging.

**Main functions & behavior**
- `finalize_invoice_logic(...)`: validates invoice items, calculates gross total with tax rules, generates invoice number, renders PDF bytes, and persists invoice + items.【F:logic.py†L73-L178】
- `export_invoices_pdf_zip(...)`: collects PDFs for invoices (prefers stored PDF, regenerates if missing) and zips them in-memory.【F:logic.py†L195-L316】
- `export_invoices_csv(...)`, `export_invoice_items_csv(...)`, `export_customers_csv(...)`: CSV exports for analytics and accounting.【F:logic.py†L338-L476】
- `export_database_backup()`: zips `storage/database.db` + invoice files for full backup.【F:logic.py†L479-L519】

**Error handling**
- Explicit `ValueError` for missing session/company or missing items ensures UI can surface actionable errors.【F:logic.py†L120-L131】【F:logic.py†L229-L243】

#### `app/services/auth.py`
**Purpose:** Authentication orchestration, token issuance, email verification, password resets.

**Main functions & behavior**
- `_hash_password()`: SHA-256 password hashing (no salt).【F:services/auth.py†L19-L21】
- `create_user_pending(...)`: creates inactive user, optional email verification token, and dispatches verification + welcome emails.【F:services/auth.py†L117-L197】
- `verify_email()`, `login_user()`, `request_password_reset()`, `reset_password()`: token validation and account state updates.【F:services/auth.py†L219-L304】

**Error handling**
- Logs warnings/errors for invalid input or email failures, but avoids hard failures on email send failures in signup flow.【F:services/auth.py†L117-L197】

#### `app/services/documents.py`
**Purpose:** File validation, metadata normalization, storage key generation, and document serialization.

**Main functions & behavior**
- `validate_document_upload()`: enforces extension whitelist and max 15 MB file size, raising `HTTPException` when invalid.【F:services/documents.py†L88-L104】
- `build_document_record()`: maps raw upload metadata into a `Document` SQLModel instance.【F:services/documents.py†L123-L164】
- `document_storage_path()` / `resolve_document_path()`: normalize storage keys into filesystem paths.【F:services/documents.py†L167-L212】
- `document_matches_filters()`: handles query/filter logic used by UI and API list endpoints.【F:services/documents.py†L231-L259】

#### `app/services/invoice_pdf.py`
**Purpose:** ReportLab PDF engine for invoice output.

**Key rendering logic**
- Builds invoice header, sender/recipient blocks, line item table, totals, and footer with bank and legal info using ReportLab’s Canvas API.【F:services/invoice_pdf.py†L101-L323】
- Auto-wraps description text to avoid overflow and handles multi-page tables by re-rendering table header on new pages.【F:services/invoice_pdf.py†L15-L78】【F:services/invoice_pdf.py†L218-L323】

---

### UI Pages (NiceGUI)

> All page renderers are located in `app/pages/`. They are navigated through `app.storage.user["page"]` and routed via `main.layout_wrapper()`.

#### `app/pages/dashboard.py`
**Purpose:** Executive summary for revenue, expenses, open invoices, and trends.

**Features**
- KPI cards for Umsatz, Ausgaben, Offen, Rechnungen.
- Revenue trend charts (ECharts) for recent months.
- “New invoice” and “Kunden ansehen” quick actions.
- Latest invoices table with click-to-open detail/editor.

**Backend links**
- Reads `Invoice`, `Customer`, `Expense` tables and aggregates totals in-memory.【F:pages/dashboard.py†L11-L239】

#### `app/pages/invoices.py`
**Purpose:** Invoice list with a 70/30 split for finalized invoices vs drafts/reminders.

**Features**
- “Neue Rechnung” button → invoice editor.
- Main table: open/finalized invoices with download/send actions and status menus.
- Drafts list with quick edit + delete.
- Reminders list for invoices older than 14 days and still open/sent.

**Backend links**
- Uses `update_status_logic`, `cancel_invoice`, and `download_invoice_file` for status changes & PDF delivery.【F:pages/invoices.py†L11-L151】

#### `app/pages/invoice_create.py`
**Purpose:** Draft + finalize invoice flow with live preview.

**Features**
- Customer selector with inline “Neuen Kunden hinzufügen”.
- Date pickers for invoice date and service period.
- VAT toggle (disabled for small-business mode).
- Line item dialog for adding positions.
- Live HTML summary + PDF preview via embedded iframe.
- “Rechnung finalisieren” triggers backend save.

**State management**
- `preview_state["dirty"]` + debounce timer controls PDF re-rendering on form changes.【F:pages/invoice_create.py†L182-L318】

**Backend links**
- Calls `finalize_invoice_logic()` to persist invoice and items, including PDF generation.【F:pages/invoice_create.py†L162-L223】

#### `app/pages/invoice_detail.py`
**Purpose:** Detailed invoice view, status, and workflow actions.

**Features**
- Status stepper (Draft → Open → Sent → Paid).
- Download / Send / PDF preview actions.
- “Edit with risk” dialog that creates a revision + new draft.
- Status transitions and corrections from the overflow menu.

**Backend links**
- Uses `update_status_logic`, `cancel_invoice`, `create_correction`, `create_invoice_revision_and_edit` for state transitions and revisions.【F:pages/invoice_detail.py†L37-L147】【F:pages/invoice_detail.py†L110-L181】

#### `app/pages/customers.py`
**Purpose:** Customer directory with card-style entries.

**Features**
- “Neu” button opens customer creation page.
- Customer cards navigate to detail page.

**Backend links**
- Reads `Customer` from active company, writes selection to session storage for detail view.【F:pages/customers.py†L6-L26】

#### `app/pages/customer_detail.py`
**Purpose:** Edit a single customer and view their invoices.

**Features**
- Editable contact/address/business details with save/cancel.
- Delete or archive customer (delete only if no invoices).
- Invoice list for the customer with click-through.

**Backend links**
- Updates customer via direct SQLModel session in `save()`. Deletes/archives with transaction checks.【F:pages/customer_detail.py†L65-L170】

#### `app/pages/customer_new.py`
**Purpose:** Create a new customer with optional address sync for recipient info.

**Features**
- Toggle to sync recipient fields from contact address.
- Save returns to invoice creation if initiated from invoice flow.

**Backend links**
- Persists `Customer` and updates session routing for return flow.【F:pages/customer_new.py†L6-L88】

#### `app/pages/documents.py`
**Purpose:** Upload, filter, and manage documents with metadata.

**Features**
- Upload (PDF/JPG/PNG, max 15 MB).
- Filters by source/type/date + search.
- Metadata dialog with raw payload + compliance flags.
- Delete confirmation.

**Backend links**
- Uses `build_document_record`, `validate_document_upload`, `blob_storage` integration, and `DocumentMeta` for metadata display.【F:pages/documents.py†L48-L318】

#### `app/pages/expenses.py`
**Purpose:** Expense CRUD with filters.

**Features**
- Create/Edit dialog with validation.
- Filters by category, date range, and search term.
- Delete confirmation dialog.

**Backend links**
- Writes to `Expense` table and logs actions with `log_audit_action` (best effort).【F:pages/expenses.py†L44-L173】

#### `app/pages/ledger.py`
**Purpose:** Unified ledger for invoices (income) and expenses.

**Features**
- Combined list of invoices + expenses with filtering by type/status/date.
- Quick open actions for invoice detail.

**Backend links**
- Uses SQL `union_all` to merge `Invoice` and `Expense` queries into a single feed.【F:pages/ledger.py†L13-L114】

#### `app/pages/exports.py`
**Purpose:** Export data (PDF/CSV/backup).

**Features**
- Export cards for PDFs, invoices CSV, items CSV, customers CSV.
- “Erweitert” section for full DB backup.

**Backend links**
- Calls `export_*` functions from `logic.py` and downloads the resulting files.【F:pages/exports.py†L6-L25】

#### `app/pages/settings.py`
**Purpose:** Company, integration, and account configuration.

**Features**
- Company switcher, create/delete company.
- Contact + address info with autocomplete.
- Logo upload.
- Business meta (small business toggle, IBAN lookup).
- Invoice numbering/filename templates.
- SMTP + n8n integration settings.
- Password change + account deletion.

**Backend links**
- Uses `services.companies` CRUD, `lookup_bank_from_iban`, and account service functions for password/account changes.【F:pages/settings.py†L34-L334】【F:pages/settings.py†L336-L482】

#### `app/pages/auth.py`
**Purpose:** Authentication UI (login, signup, verify, reset).

**Features**
- Login / Signup / Verify email / Password reset flows.
- Inline validation and success state transitions.

**Backend links**
- Calls `services.auth` for verification, login, and reset flows.【F:pages/auth.py†L35-L240】

---

## 🧠 Features & Business Logic Deep Dive

### Invoice lifecycle
- **Draft → Open → Sent → Paid** (plus **Finalized/Cancelled**).
- Status transitions are driven by `update_status_logic` in UI menus and are surfaced in status badges/stepper components.【F:pages/invoices.py†L48-L96】【F:pages/_shared.py†L458-L496】

### “Edit with Risk” revision system
- `create_invoice_revision_and_edit()` snapshots the original invoice + items into `InvoiceRevision`, then spawns a new draft tied via `related_invoice_id`.
- This preserves an audit trail while allowing corrections without mutating a finalized invoice directly.【F:pages/_shared.py†L350-L437】

### PDF generation
- **ReportLab engine (`services/invoice_pdf.py`)** renders final PDFs with explicit drawing commands (Canvas), line wrapping, and dynamic table rows.【F:services/invoice_pdf.py†L101-L323】
- **HTML preview + FPDF renderer** in `invoice_create` provides a live embedded preview using `PDFInvoiceRenderer` and `build_invoice_preview_html` for summary text.【F:pages/invoice_create.py†L215-L308】【F:pages/invoice_utils.py†L31-L75】【F:renderer.py†L1-L120】

### n8n integration & HMAC verification
- `/api/webhooks/n8n/ingest` requires an **HMAC SHA-256 signature** in `X-Signature`, based on `X-Timestamp` + raw body, with 5-minute drift tolerance.

```python
signed_payload = f"{timestamp_header}.".encode("utf-8") + raw_body
expected_signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected_signature, signature):
    raise HTTPException(status_code=401, detail="Invalid signature")
```

This ensures payload integrity and prevents replay attacks via timestamp checks and `WebhookEvent` idempotency tracking.【F:main.py†L175-L315】

---

## 🔐 Security & Error Handling

### Authentication & session guarding
- `require_auth()` redirects unauthenticated users to `/login` and protects API routes that call `_require_api_auth()` or `require_auth()` directly.【F:auth_guard.py†L1-L10】【F:main.py†L61-L70】

### Validation
- Document uploads are validated by extension and size (15 MB max), raising `HTTPException` for invalid inputs, which are surfaced in the UI with `ui.notify`.
  【F:services/documents.py†L88-L104】【F:pages/documents.py†L67-L125】

### Error handling strategy
- **UI-level feedback:** Most UI actions catch exceptions and show `ui.notify` messages, preventing crashes and ensuring user visibility (e.g., invoice download/send, document upload).【F:pages/invoices.py†L38-L76】【F:pages/documents.py†L67-L140】
- **System logging:** `services/auth.py` logs warnings/errors for verification and email failures without breaking the signup flow.【F:services/auth.py†L117-L197】
- **API errors:** FastAPI endpoints consistently raise `HTTPException` for unauthorized/invalid input, producing clear HTTP responses for integrations.【F:main.py†L61-L520】

---

## 🛠️ Setup & Deployment

### Docker production setup
1. Copy `.env.example` to `.env` and fill in domains + storage secret:
   - `APP_DOMAIN`, `N8N_DOMAIN`, `STORAGE_SECRET`.
2. Start the production stack:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
3. Caddy provisions TLS automatically for the configured subdomains.

**Data locations**
- App data: `app_storage` volume → `/app/storage` (SQLite DB + invoices).【F:DEPLOYMENT.md†L11-L18】【F:docker-compose.prod.yml†L1-L14】
- n8n data: `n8n_data` volume → `/home/node/.n8n`.【F:DEPLOYMENT.md†L11-L18】【F:docker-compose.prod.yml†L15-L30】

### Native (Windows/macOS/Linux) setup
- Use `start_native.ps1` (Windows) or `start_native.sh` (macOS/Linux). Both set up Python, install dependencies, and optionally start n8n if Node is installed.【F:start_native.sh†L1-L92】

### Environment variables

| Variable | Used by | Purpose / Notes |
| --- | --- | --- |
| `APP_DOMAIN` | Caddy + docker-compose.prod | Public hostname for the app (TLS routing).【F:Caddyfile†L1-L6】【F:docker-compose.prod.yml†L1-L41】 |
| `N8N_DOMAIN` | Caddy + docker-compose.prod | Public hostname for n8n (TLS routing + webhook base URLs).【F:Caddyfile†L1-L6】【F:docker-compose.prod.yml†L15-L41】 |
| `APP_BASE_URL` | app/main.py + services/auth + address autocomplete | Base URL for building email links and internal API calls. Defaults to `http://localhost:8080`.【F:docker-compose.prod.yml†L1-L14】【F:services/auth.py†L69-L76】【F:pages/_shared.py†L132-L147】 |
| `STORAGE_SECRET` | NiceGUI app | Session signing secret (must be changed in prod).【F:docker-compose.prod.yml†L1-L14】【F:main.py†L1102-L1108】 |
| `REQUIRE_EMAIL_VERIFICATION` | services/auth | Forces email verification when set to `1`.【F:services/auth.py†L23-L35】 |
| `SEND_WELCOME_EMAIL` | services/auth | Enables welcome email when set to `1`.【F:services/auth.py†L100-L110】 |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` | services/email | SMTP configuration for sending verification/reset emails.【F:services/email.py†L14-L37】 |
| `STORAGE_BACKEND` | services/blob_storage | Choose `local` (default) or `s3` blob storage backend.【F:services/blob_storage.py†L175-L184】 |
| `STORAGE_LOCAL_ROOT` | services/blob_storage, services/documents | Root directory for local storage (default `storage`).【F:services/blob_storage.py†L178-L184】【F:services/documents.py†L167-L212】 |
| `S3_BUCKET` / `S3_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `S3_ENDPOINT_URL` | services/blob_storage | S3-compatible configuration when `STORAGE_BACKEND=s3`.【F:services/blob_storage.py†L122-L130】 |
| `TZ` | docker-compose | Container timezone (app and n8n).【F:docker-compose.yml†L8-L24】【F:docker-compose.prod.yml†L6-L27】 |
| `N8N_*` variables (`N8N_HOST`, `N8N_PROTOCOL`, `N8N_PORT`, `N8N_EDITOR_BASE_URL`, `WEBHOOK_URL`, `N8N_SECURE_COOKIE`, `EXECUTIONS_DATA_*`, `N8N_DEFAULT_BINARY_DATA_MODE`) | n8n container | n8n runtime configuration in prod compose (TLS + pruning).【F:docker-compose.prod.yml†L15-L30】 |
| `ALLOWED_HOSTS` | dev compose | Set to `*` in dev for permissive access (not used in prod compose).【F:docker-compose.yml†L6-L11】 |

**Note:** There is no `DB_PASSWORD` or Postgres/Redis configuration in this repo; the app and n8n both default to local SQLite-backed persistence unless you customize the stack.【F:docker-compose.prod.yml†L1-L50】【F:data.py†L174-L181】

---

## 📌 Error Handling Summary (Quick Index)

<details>
<summary>Where errors are handled</summary>

- **UI feedback (`ui.notify`)**: invoice actions, document upload/deletion, expense editing, customer mutations.【F:pages/invoices.py†L38-L96】【F:pages/documents.py†L67-L240】【F:pages/expenses.py†L80-L180】
- **Logging (`logging`):** auth flows emit structured warnings/errors but keep UX intact.【F:services/auth.py†L117-L197】
- **API errors (`HTTPException`)**: webhook validation, document API validation, auth guards.【F:main.py†L150-L520】【F:services/documents.py†L88-L104】

</details>

---

## 📦 Appendix: Additional Notes

- **Invoice finalization** uses `finalize_invoice_logic()` to build PDF bytes immediately and persist them into the invoice record (`pdf_bytes`).【F:logic.py†L143-L178】
- **Address autocomplete** is implemented in `main.py` + `pages/_shared.py`, calling OpenStreetMap’s Nominatim API and returning structured address parts.【F:main.py†L88-L147】【F:pages/_shared.py†L121-L214】
