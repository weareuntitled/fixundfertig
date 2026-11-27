"""Zugang zu den Belegsummen für Aufrufer mit Datenbank (#506).

Sammelt zu einem gespeicherten Beleg die Eingaben des Moduls Belegsummen:
Positionen, Steuersatz (bei Altbelegen abgeleitet), Kleinunternehmer-Status der
Firma und bei einer Schlussrechnung die festgehaltenen Abzüge. Gerechnet wird
ausschließlich in ``logic.belegsummen``.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session

from data import Company, Invoice
from logic.belegsummen import Abschlag, Belegsummen, Position, belegsummen, legacy_vat_rate
from logic.final_invoice import final_deductions


def invoice_positions(invoice: Invoice) -> list[Position]:
    return [Position(quantity=it.quantity, unit_price=it.unit_price) for it in (invoice.items or [])]


def invoice_vat_rate(invoice: Invoice) -> Decimal:
    """Gespeicherter Steuersatz des Belegs; bei Altbelegen ohne Satz abgeleitet."""
    stored = getattr(invoice, "vat_rate", None)
    if stored is not None:
        return Decimal(str(float(stored)))
    return legacy_vat_rate(invoice_positions(invoice), stored_gross=invoice.total_brutto)


def _company(invoice: Invoice, session: Optional[Session]) -> Any:
    if session is not None and getattr(invoice, "company_id", None):
        return session.get(Company, int(invoice.company_id))
    # Nur eine bereits geladene Firma; ein abgelöster Beleg lädt nichts nach.
    return vars(invoice).get("company")


def belegsummen_for_invoice(invoice: Invoice, session: Optional[Session] = None) -> Belegsummen:
    """Belegsummen eines gespeicherten Belegs.

    Eine Schlussrechnung liest ihre festgehaltenen Abzüge; sind sie beschädigt,
    wirft ``final_deductions`` einen ``ValueError`` mit deutscher Meldung.
    """
    deductions = None
    if bool(getattr(invoice, "is_final_invoice", False)):
        deductions = [
            Abschlag(id=row.id, nr=row.nr, date=row.date, net=row.net, tax=row.tax)
            for row in final_deductions(invoice)
        ]
        # Eine Schlussrechnung behält ihren beim Anlegen festgehaltenen Satz
        # (Kleinunternehmer: 0), auch wenn sich der Status der Firma später ändert.
        charges_vat = True
    else:
        company = _company(invoice, session)
        charges_vat = not bool(getattr(company, "is_small_business", False))
    return belegsummen(
        invoice_positions(invoice),
        vat_rate=invoice_vat_rate(invoice),
        charges_vat=charges_vat,
        deductions=deductions,
    )
