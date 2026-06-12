# =========================
# APP/API/LEDGER.PY
# =========================
"""
Combined Ledger API: /api/ledger

Returns a unified, date-sorted list of all income (invoices) and expenses for
the current company. Useful for accounting views ("Buchhaltung").

Output shape (per entry):
- type:        "invoice" | "expense"
- date:        ISO date string (YYYY-MM-DD)
- description: human-readable label (invoice title or expense description/category)
- amount:      float (always positive; type indicates sign convention)
- id:          invoice_id or expense_id
"""

from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, Query
from sqlmodel import select

from data import Expense, Invoice
from dependencies import db_session, get_current_company, require_session_auth


router = APIRouter(prefix="/api/ledger", tags=["ledger"])


@router.get("")
def list_ledger(
    year: int | None = Query(default=None, ge=2000, le=2100),
    _user_id: int = Depends(require_session_auth),
    company=Depends(get_current_company),
    session: Iterator = Depends(db_session),
):
    """List all invoices + expenses for the current company, sorted by date desc."""
    entries: list[dict] = []

    inv_stmt = select(Invoice).where(Invoice.company_id == int(company.id))
    if year is not None:
        inv_stmt = inv_stmt.where(Invoice.date.startswith(f"{int(year)}-"))
    for inv in session.exec(inv_stmt).all():
        entries.append({
            "type": "invoice",
            "id": int(inv.id),
            "date": inv.date or "",
            "description": f"{inv.title or 'Rechnung'} · {inv.nr or ''}".strip(" ·"),
            "amount": float(inv.total_brutto or 0.0),
        })

    exp_stmt = select(Expense).where(Expense.company_id == int(company.id))
    if year is not None:
        exp_stmt = exp_stmt.where(Expense.date.startswith(f"{int(year)}-"))
    for exp in session.exec(exp_stmt).all():
        entries.append({
            "type": "expense",
            "id": int(exp.id),
            "date": exp.date or "",
            "description": f"{exp.category}: {exp.description}".strip(": "),
            "amount": float(exp.amount or 0.0),
        })

    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries
