# =========================
# APP/API/EXPORTS.PY
# =========================
"""
Export API: /api/exports/*

Endpoints:
- GET /api/exports/customers-csv      — Customers CSV
- GET /api/exports/invoices-csv       — Invoices CSV (year query param)
- GET /api/exports/items-csv          — Invoice items CSV (year query param)
- GET /api/exports/invoices-pdf       — Invoices PDF ZIP (year query param)
- GET /api/exports/db-backup          — Database backup ZIP

Backing: `app/logic.py` (`export_invoices_pdf_zip`, `export_invoices_csv`,
`export_invoice_items_csv`, `export_customers_csv`, `export_database_backup`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterator

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from data import get_session
from dependencies import get_current_company, require_session_auth
from logic import (
    export_customers_csv,
    export_database_backup,
    export_invoice_items_csv,
    export_invoices_csv,
    export_invoices_pdf_zip,
)


router = APIRouter(prefix="/api/exports", tags=["exports"])


def _csv_response(csv_bytes: bytes, filename: str) -> Response:
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _zip_response(zip_bytes: bytes, filename: str) -> Response:
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/customers-csv", response_class=Response)
def customers_csv(
    _user_id: int = Depends(require_session_auth),
    company=Depends(get_current_company),
):
    """Download all customers for the current company as CSV."""
    with get_session() as session:
        csv_bytes = export_customers_csv(session, int(company.id))
    return _csv_response(csv_bytes, "customers.csv")


@router.get("/invoices-csv", response_class=Response)
def invoices_csv(
    year: int = Query(default_factory=lambda: datetime.now().year, ge=2000, le=2100),
    _user_id: int = Depends(require_session_auth),
    company=Depends(get_current_company),
):
    """Download invoices for the given year as CSV."""
    with get_session() as session:
        csv_bytes = export_invoices_csv(session, int(company.id), year=year)
    return _csv_response(csv_bytes, f"invoices-{year}.csv")


@router.get("/items-csv", response_class=Response)
def items_csv(
    year: int = Query(default_factory=lambda: datetime.now().year, ge=2000, le=2100),
    _user_id: int = Depends(require_session_auth),
    company=Depends(get_current_company),
):
    """Download invoice line items for the given year as CSV."""
    with get_session() as session:
        csv_bytes = export_invoice_items_csv(session, int(company.id), year=year)
    return _csv_response(csv_bytes, f"items-{year}.csv")


@router.get("/invoices-pdf", response_class=Response)
def invoices_pdf(
    year: int = Query(default_factory=lambda: datetime.now().year, ge=2000, le=2100),
    _user_id: int = Depends(require_session_auth),
    company=Depends(get_current_company),
):
    """Download all invoice PDFs for the given year as a ZIP."""
    with get_session() as session:
        zip_bytes = export_invoices_pdf_zip(session, int(company.id), year=year)
    return _zip_response(zip_bytes, f"invoices-{year}.zip")


@router.get("/db-backup", response_class=Response)
def db_backup(
    _user_id: int = Depends(require_session_auth),
    company=Depends(get_current_company),
):
    """Download a full database backup (DB file + invoice PDFs) as a ZIP."""
    with get_session() as session:
        zip_bytes = export_database_backup(session, int(company.id))
    return _zip_response(zip_bytes, f"backup-{datetime.now().strftime('%Y-%m-%d')}.zip")
