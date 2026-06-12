# =========================
# APP/API/__INIT__.PY
# =========================
"""
FastAPI Router Aggregation.

Each domain module in `app/api/` exposes an `APIRouter` instance.
This package re-exports them and exposes a single `api_router`
that `app/main.py` mounts once on the FastAPI app.

Convention:
- Each `app/api/<domain>.py` defines `router = APIRouter(prefix=..., tags=[...])`
- This __init__.py collects them into `api_router`
- main.py: `app.include_router(api_router)`

Wächst inkrementell mit jeder Extraktion. Stand 2026-06-10: internal, customers.
"""

import sys
from pathlib import Path as _Path

# Repo-Konvention: interne Imports ohne `app.`-Prefix (`from auth_guard`, `from data`,
# `from services.*`, etc.). Damit das auch unter `app.api.*` funktioniert, müssen
# `app/` und `app/api/` im sys.path liegen, sodass alle Submodule als top-level
# Module geladen werden (z.B. `dependencies` statt `app.api.dependencies`).
# Wichtig: niemals `from app.api.<X> import` — sonst gibt's Doppel-Modul-Instanzen
# und SQLAlchemy Table-Konflikte.
_APP_ROOT = _Path(__file__).resolve().parent.parent
_API_ROOT = _Path(__file__).resolve().parent
for _p in (_APP_ROOT, _API_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Erst JETZT (nach sys.path-Setup) die Submodule importieren.
from fastapi import APIRouter
from internal import router as internal_router  # noqa: E402
from customers import router as customers_router  # noqa: E402
from auth import router as auth_router  # noqa: E402
from invoices import router as invoices_router  # noqa: E402
from documents import router as documents_router  # noqa: E402
from expenses import router as expenses_router  # noqa: E402
from invites import router as invites_router  # noqa: E402
from exports import router as exports_router  # noqa: E402
from ledger import router as ledger_router  # noqa: E402
from companies import router as companies_router  # noqa: E402

api_router = APIRouter()
api_router.include_router(internal_router)
api_router.include_router(customers_router)
api_router.include_router(auth_router)
api_router.include_router(invoices_router)
api_router.include_router(documents_router)
api_router.include_router(expenses_router)
api_router.include_router(invites_router)
api_router.include_router(exports_router)
api_router.include_router(ledger_router)
api_router.include_router(companies_router)

__all__ = ["api_router"]
