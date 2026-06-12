<!-- refreshed: 2026-05-05 -->
# External Integrations

**Analysis Date:** 2026-05-05

## APIs & External Services

**Automation & Webhooks:**
- **n8n** - Workflow automation platform
  - SDK/Client: `app/integrations/n8n_client.py`, native HTTP
  - Auth: `X-N8N-Secret` header or HMAC signature
  - Usage: Document ingestion, automated invoice processing

**Address Services:**
- **OpenStreetMap Nominatim** - Address autocomplete
  - Endpoint: `https://nominatim.openstreetmap.org/search`
  - Usage: Address autocomplete in customer forms
  - Rate Limit: Subject to Nominatim usage policy

**Cloud Storage:**
- **AWS S3** (via boto3) - Blob storage for documents
  - SDK/Client: `boto3==1.42.24`
  - Implementation: `app/services/blob_storage.py`
  - Auth: AWS credentials via environment

## Data Storage

**Databases:**
- **SQLite** (default)
  - Location: `storage/database.db`
  - Client: SQLModel with SQLAlchemy engine
  - Tables: User, Company, Customer, Invoice, Document, Token, InvitedEmail, WebhookEvent

- **PostgreSQL** (for n8n)
  - Used by: n8n service in production compose
  - Credentials: Via `DB_PASSWORD` environment variable

**File Storage:**
- **Local filesystem** (default for app)
  - Path: `storage/invoices/`, `storage/documents/`
  - Implementation: Direct file I/O

- **AWS S3** (optional)
  - Implementation: `app/services/blob_storage.py`
  - Config: Via `app/services/storage.py:blob_storage()` factory

**Caching:**
- **Redis** (optional)
  - URL: Via `REDIS_URL` environment variable
  - Usage: Session caching, rate limiting

## Authentication & Identity

**Auth Provider:**
- Custom session-based authentication
  - Implementation: `app/services/auth.py`
  - Session storage: Server-side with signed cookies
  - Password hashing: bcrypt via passlib

**Owner Bootstrap:**
- Environment-based initial user creation
  - Variables: `OWNER_EMAIL`, `OWNER_PASSWORD`
  - Implementation: `app/services/auth.py:ensure_owner_user()`

## Monitoring & Observability

**Error Tracking:**
- Not detected (no external error tracking service)

**Logs:**
- Python standard logging (`logging` module)
- Implementation: `app/logging_setup.py`

## CI/CD & Deployment

**Hosting:**
- Docker (primary)
- Docker Compose for orchestration

**CI Pipeline:**
- GitHub Actions (`.github/workflows/main.yml`)
  - Workflow: Main CI pipeline

**Production Services:**
- Caddy 2 - Reverse proxy with automatic TLS
- n8n - Automation (separate service)
- PostgreSQL - For n8n data (separate service)
- Redis - Optional caching (separate service)

## Environment Configuration

**Required env vars:**
- `OWNER_EMAIL` - Initial owner account email
- `OWNER_PASSWORD` - Initial owner account password
- `APP_DOMAIN` - Production domain
- `STORAGE_SECRET` - Session signing secret (min 32 chars)

**Optional env vars:**
- `APP_BASE_URL` - Full application URL
- `REDIS_URL` - Redis connection for caching
- `N8N_SECRET` - n8n integration secret
- Various SMTP settings for email

## Webhooks & Callbacks

**Incoming:**
- `/api/webhooks/n8n/ingest` - n8n document ingestion (POST, HMAC signed)
- `/api/webhooks/n8n/upload` - Alternative n8n upload endpoint (multipart form)

**Outgoing:**
- `n8n_webhook_url` - Per-company webhook URL for invoice events (stored in Company model)

---

*Integration audit: 2026-05-05*