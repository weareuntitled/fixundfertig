# =========================
# APP/API/CUSTOMERS.PY
# =========================
"""
Customer CRUD API: /api/customers[/...]

Endpoints:
- GET    /api/customers            — Liste (gefiltert nach Company)
- POST   /api/customers            — Erstellen
- GET    /api/customers/{id}       — Detail
- PUT    /api/customers/{id}       — Update (partial via CustomerUpdate)
- DELETE /api/customers/{id}       — Löschen (nur wenn keine Invoices)

Auth: Session-basiert via `dependencies.require_session_auth`.
Wird in M2 auf JWT umgestellt (nur die Dependency, nicht die Endpoints).
"""

from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from data import Customer, Invoice
from dependencies import db_session, get_current_company, require_session_auth
from schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate


router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerRead])
def list_customers(
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """List all customers for the current company."""
    statement = select(Customer).where(Customer.company_id == int(company.id))
    customers = session.exec(statement).all()
    return [CustomerRead.model_validate(c) for c in customers]


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Create a new customer for the current company. `kdnr=0` (dead field, see audit U7)."""
    new_customer = Customer(
        company_id=int(company.id),
        kdnr=0,
        **payload.model_dump(exclude={"archived"}),
    )
    if payload.archived:
        new_customer.archived = True
    session.add(new_customer)
    session.commit()
    session.refresh(new_customer)
    return CustomerRead.model_validate(new_customer)


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Get one customer by id."""
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return CustomerRead.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Partial-update a customer. Only fields present in the payload are changed."""
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(customer, key, value)
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return CustomerRead.model_validate(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Delete a customer — only allowed if no invoices reference them."""
    customer = session.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    invoice_count = session.exec(
        select(Invoice).where(Invoice.customer_id == customer_id)
    ).first()
    if invoice_count is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer has invoices — archive instead of delete",
        )
    session.delete(customer)
    session.commit()
    return None
