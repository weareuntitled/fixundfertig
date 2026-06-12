# FixundFertig System Prompt

**A German invoicing/ERP SaaS platform built with Python (NiceGUI + FastAPI).**

---

## What It Does

- Create and manage invoices (German-style with tax calculations)
- Customer relationship management
- Document storage and ingestion
- PDF invoice generation
- Webhook automation via n8n

---

## Stack

| Layer | Technology |
|-------|-----------|
| Web Framework | NiceGUI + FastAPI (Python 3.11+) |
| Database | SQLite (default) / PostgreSQL (prod) |
| ORM | SQLModel |
| PDF | ReportLab, fpdf2 |
| Storage | Local filesystem or AWS S3 |
| Automation | n8n |
| Proxy | Caddy 2 |
| Runtime | Docker |

---

## The Architecture

A **monolithic Python web app** that handles both:
- **UI** → NiceGUI pages served via WebSocket
- **API** → FastAPI REST endpoints

Behind **Caddy** reverse proxy (TLS termination).

```
Client → Caddy (:443) → FixundFertig (:8080) → SQLite + File Storage
                              ↘ n8n webhook integration
```

---

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | Entry point (~2000 lines) |
| `app/data.py` | SQLModel database models |
| `app/pages/*.py` | NiceGUI UI renderers |
| `app/services/*.py` | Business logic |
| `app/renderer.py` | PDF generation |

---

## Integrations

- **n8n** → Documents via HMAC-signed webhooks (`/api/webhooks/n8n/ingest`)
- **AWS S3** → Optional blob storage
- **PostgreSQL** → Production database for n8n
- **Redis** → Optional caching

---

## Running It

```bash
# Development
python app/main.py

# Production (Docker)
docker-compose -f docker-compose.prod.yml up
```

---

## Quick Context

- **Language**: German (invoices, UI labels)
- **Auth**: Session-based with HMAC-signed cookies
- **Multi-tenancy**: Single DB with `company_id` foreign keys
- **No external auth**: Own user system with owner bootstrap via env vars

---

*Use this as system context for code analysis or refactoring.*