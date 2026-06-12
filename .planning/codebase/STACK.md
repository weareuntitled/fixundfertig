<!-- refreshed: 2026-05-05 -->
# Technology Stack

**Analysis Date:** 2026-05-05

## Languages

**Primary:**
- Python 3.11+ - Main application language for backend, API, and UI

**Secondary:**
- HTML/JavaScript (via NiceGUI) - Generated automatically by NiceGUI framework

## Runtime

**Environment:**
- Python 3.11+ (as specified in `pyproject.toml:requires-python`)

**Package Manager:**
- pip (via `requirements.txt`)
- uv (optional, recommended in README)
- Lockfile: Not present (pip without lock file)

## Frameworks

**Core:**
- **NiceGUI 3.5.0** - Python UI framework (built on Vue.js), serves both UI and API
- **FastAPI 0.128.0** - REST API framework, mounted within NiceGUI app

**Database:**
- **SQLAlchemy 2.0.45** - ORM for database operations
- **SQLModel 0.0.31** - Pydantic + SQLAlchemy integration layer

**PDF Generation:**
- **ReportLab 4.4.7** - Primary PDF generation
- **fpdf2 2.8.5** - Alternative PDF generation

**Testing:**
- **pytest** - Test runner (from optional dependencies)

**Build/Dev:**
- **uvicorn** - ASGI server for running the app

## Key Dependencies

**Critical:**
- `nicegui==3.5.0` - Core UI/API framework
- `fastapi==0.128.0` - REST API capabilities
- `sqlmodel==0.0.31` - Database ORM with Pydantic
- `reportlab==4.4.7` - PDF invoice generation

**Infrastructure:**
- `boto3==1.42.24` - AWS S3 blob storage integration
- `redis` - Caching layer (optional via REDIS_URL)
- `passlib[bcrypt]` - Password hashing
- `python-dotenv` - Environment variable loading
- `pandas==2.3.3` - Data processing

**Security:**
- `pydantic==2.12.5` - Data validation

## Configuration

**Environment:**
- `.env` file with variables like:
  - `OWNER_EMAIL`, `OWNER_PASSWORD` - Initial owner account
  - `APP_BASE_URL` - Application URL
  - `APP_DOMAIN` - Domain name for production
  - `STORAGE_SECRET` - Session signing secret
  - `N8N_SECRET` - n8n integration secret

**Build:**
- `pyproject.toml` - Python project configuration with dependencies
- `Dockerfile` - Docker image build instructions
- `docker-compose.prod.yml` - Production service orchestration

## Platform Requirements

**Development:**
- Python 3.11+
- Local SQLite (built-in)
- Optional: Docker for containerized development

**Production:**
- Docker & Docker Compose
- Caddy (reverse proxy with TLS)
- Optional: PostgreSQL (for n8n), Redis (for caching)

---

*Stack analysis: 2026-05-05*