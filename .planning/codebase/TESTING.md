<!-- refreshed: 2026-05-05 -->
# Testing Patterns

**Analysis Date:** 2026-05-05

## Test Framework

**Runner:**
- **pytest** - Configured in `pyproject.toml` as optional test dependency
- Version: Not pinned (from requirements.txt or pyproject.toml)
- Config: Not detected (no pytest.ini, pyproject.toml has only test dependency)

**Assertion Library:**
- pytest built-in assertions

**Run Commands:**
```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest -k test_name      # Run specific test
```

## Test File Organization

**Location:**
- `tests/` directory in project root
- Co-located with application code

**Naming:**
- `test_*.py` pattern for test files

**Structure:**
```
tests/
├── conftest.py          # pytest fixtures
├── test_readonly_share.py
├── test_invoice_utils.py
├── test_port_configuration.py
├── test_invoice_customer_merge.py
├── test_invoice_pdf.py
├── test_invoice_calculations.py
├── test_finalize_invoice_logic.py
├── test_documents_ingest.py
```

## Test Structure

**Suite Organization:**
- pytest test functions in `test_*.py` files
- Fixtures defined in `conftest.py`

**Patterns:**
- Setup: Use pytest fixtures for common setup
- Teardown: Implicit via pytest
- Assertion: Standard pytest assertions

## Mocking

**Framework:** Not explicitly configured

**Patterns:**
- Detected usage: `nicegui.helpers.is_pytest()` check in `app/main.py:103`

**What to Mock:**
- Database sessions (not detected in test files)
- External services (not detected)

**What NOT to Mock:**
- Application logic that needs integration testing

## Fixtures and Factories

**Test Data:**
- Tests appear to use direct test data (not extensive fixtures detected)
- No factory library detected (no factory_boy)

**Location:**
- `tests/conftest.py` - pytest configuration and fixtures

## Coverage

**Requirements:** None enforced

**View Coverage:** Not configured

## Test Types

**Unit Tests:**
- Individual function testing
- Examples from test files: `test_port_configuration.py`, `test_invoice_utils.py`

**Integration Tests:**
- Appear to test components together
- Examples: `test_documents_ingest.py`, `test_finalize_invoice_logic.py`

**E2E Tests:**
- Not detected (no Playwright, Selenium, or similar)

## Common Patterns

**Async Testing:**
- Not extensively used (application uses synchronous NiceGUI handlers)

**Error Testing:**
- Detected in tests via pytest assertions

---

*Testing analysis: 2026-05-05*