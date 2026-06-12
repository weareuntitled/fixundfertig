# =========================
# APP/API/EXPENSES.PY
# =========================
"""
Expense API: /api/expenses[/...]

Endpoints:
- GET    /api/expenses         — Liste (für current company)
- POST   /api/expenses         — Erstellen
- DELETE /api/expenses/{id}    — Löschen
"""

from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from data import Expense
from dependencies import db_session, get_current_company, require_session_auth
from schemas.expense import ExpenseCreate, ExpenseRead


router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseRead])
def list_expenses(
    _user_id: int = Depends(require_session_auth),
    company=Depends(get_current_company),
    session: Iterator = Depends(db_session),
):
    """List all expenses for the current company."""
    expenses = session.exec(
        select(Expense).where(Expense.company_id == int(company.id))
    ).all()
    return [ExpenseRead.model_validate(e) for e in expenses]


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Create a new expense for the current company."""
    new_expense = Expense(
        company_id=int(company.id),
        date=payload.date,
        category=payload.category,
        description=payload.description,
        amount=payload.amount,
        source="MANUAL",
    )
    session.add(new_expense)
    session.commit()
    session.refresh(new_expense)
    return ExpenseRead.model_validate(new_expense)


@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Delete an expense by id."""
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    session.delete(expense)
    session.commit()
    return {"status": "deleted"}
