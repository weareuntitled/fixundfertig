"""Hilfslogik: frisch angelegten Kunden in Rechnungserstellung-Auswahl aufnehmen."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from data import Customer


def parse_new_customer_id(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def merge_customer_from_new_id(
    session: Session,
    *,
    comp_id: int,
    all_customers: List[Any],
    customers_by_id: Dict[int, Any],
    new_customer_id: Optional[int],
) -> None:
    """
    Wenn new_customer_id gesetzt ist, aber noch nicht in customers_by_id:
    Kundenzeile aus der DB laden (nur gleiche Company, nicht archiviert) und Listen ergänzen.
    """
    if new_customer_id is None:
        return
    if int(new_customer_id) in customers_by_id:
        return
    stmt = select(Customer).where(
        Customer.company_id == int(comp_id),
        Customer.archived == False,  # noqa: E712
        Customer.id == int(new_customer_id),
    )
    new_customer = session.exec(stmt).first()
    if new_customer:
        all_customers.append(new_customer)
        customers_by_id[int(new_customer.id)] = new_customer
