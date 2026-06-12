<!-- refreshed: 2026-05-05 -->
# Codebase Concerns

**Analysis Date:** 2026-05-05

## Tech Debt

**Large main.py file:**
- Issue: `app/main.py` has grown to 2000+ lines containing both FastAPI routes and page handlers
- Files: `app/main.py`
- Impact: Hard to navigate, maintain, and test; unclear separation of concerns
- Fix approach: Split into `api.py` for endpoints and keep only app initialization in `main.py`

**Duplicate environment loading:**
- Issue: `load_env()` called in multiple places (`app/main.py`, `app/data.py`, `app/env.py`)
- Files: `app/main.py:32-35`, `app/data.py:16`, `app/env.py`
- Impact: Potential race conditions, unclear initialization order
- Fix approach: Single entry point for env loading before any other imports

**Inline SQL queries throughout:**
- Issue: Direct `session.exec(select(...))` calls in `main.py` and services
- Files: `app/main.py` (multiple locations), `app/services/*.py`
- Impact: Business logic mixed with data access, harder to test
- Fix approach: Use repository pattern with dedicated data access methods

## Known Bugs

**No bugs explicitly documented:**
- No TODO/FIXME/HACK comments detected in codebase
- No explicit bug tracking (not integrated with issue tracker)

## Security Considerations

**Session secret in development:**
- Risk: Default session secret "pytest-secret" used in test mode
- Files: `app/main.py:129-137`
- Current mitigation: Only used when `_IS_PYTEST` is True
- Recommendations: Ensure production always sets `STORAGE_SECRET` with strong value

**Webhook signature validation:**
- Risk: HMAC-based auth for n8n webhooks with timing-sensitive comparison
- Files: `app/main.py:716-724`
- Current mitigation: Uses `hmac.compare_digest()` to prevent timing attacks
- Recommendations: Continue using secure comparison method

## Performance Bottlenecks

**PDF generation on demand:**
- Problem: Generated on each request if not cached
- Files: `app/main.py:420-438`, `app/renderer.py`
- Cause: No background generation, synchronous on-request
- Improvement path: Add background task queue for PDF generation

**No query optimization:**
- Problem: Full table scans in list endpoints
- Files: `app/main.py:1284-1310` (documents list)
- Cause: No pagination, filtering done in Python after full fetch
- Improvement path: Add database-level filtering and pagination

## Fragile Areas

**File storage path resolution:**
- Files: `app/main.py:450-463`, `app/services/storage.py`
- Why fragile: Complex path resolution logic with security checks
- Safe modification: Ensure path stays within storage root
- Test coverage: Limited (tests for storage exist but may miss edge cases)

**n8n webhook payload parsing:**
- Files: `app/main.py:319-405` (Pydantic models), `app/main.py:660-868`
- Why fragile: Multiple validation layers, backward compatibility handling
- Safe modification: Add comprehensive validation tests
- Test coverage: `tests/test_documents_ingest.py` exists

## Scaling Limits

**SQLite single-writer:**
- Current capacity: Single application instance works well
- Limit: Multiple concurrent writes will cause locking
- Scaling path: Migrate to PostgreSQL for concurrent access

**Local file storage:**
- Current capacity: Single server with local disk
- Limit: Doesn't work in distributed/multi-instance deployment
- Scaling path: Use S3-compatible blob storage (already implemented)

## Dependencies at Risk

**No deprecated packages detected:**
- All dependencies are current versions
- boto3, fastapi, nicegui all actively maintained

## Missing Critical Features

**Type checking:**
- Problem: No enforced type checking in CI
- Blocks: Catching type errors before production
- Missing: mypy integration in CI pipeline

**Code formatting:**
- Problem: No automatic code formatting
- Blocks: Inconsistent code style
- Missing: ruff or black formatter in pre-commit or CI

## Test Coverage Gaps

**No test coverage reporting:**
- What's not tested: No coverage measurement configured
- Files: All source files
- Risk: Untested code paths not detected
- Priority: Medium

**Limited E2E testing:**
- What's not tested: Full user workflows
- Files: UI interactions
- Risk: Integration issues between components
- Priority: Low (NiceGUI provides some built-in testing)

---

*Concerns audit: 2026-05-05*