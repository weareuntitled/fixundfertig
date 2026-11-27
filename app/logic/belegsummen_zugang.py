"""Zugang zu den Belegsummen für Aufrufer mit Datenbank und für die Darstellung (#506, #508).

Sammelt zu einem Beleg die Eingaben des Moduls Belegsummen: Positionen,
Steuersatz (bei Altbelegen abgeleitet), Kleinunternehmer-Status der Firma, den
USt-Schalter eines Entwurfs und bei einer Schlussrechnung die festgehaltenen
Abzüge. Gerechnet wird ausschließlich in ``logic.belegsummen``.

Ein Beleg darf ein gespeicherter ``Invoice``, ein Entwurf als Dict oder eine
Vorschau (``SimpleNamespace``) sein; PDF und E-Mail rufen diesen Zugang, wenn
ihr Aufrufer ihnen keine fertigen Belegsummen mitgibt.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from sqlmodel import Session

from data import Company
from logic.belegsummen import Abschlag, Belegsummen, Position, belegsummen, legacy_vat_rate
from logic.final_invoice import final_deductions
from services.invoice_pdf_layout import document_items


def _field(document: Any, *names: str) -> Any:
    """Erster gesetzter Wert (nicht None, nicht leer) aus Dict oder Objekt."""
    for name in names:
        value = document.get(name) if isinstance(document, dict) else getattr(document, name, None)
        if value not in (None, ""):
            return value
    return None


def invoice_positions(document: Any) -> list[Position]:
    return [
        Position(quantity=_field(item, "quantity", "qty") or 0, unit_price=_field(item, "unit_price", "price") or 0)
        for item in document_items(document)
    ]


def invoice_vat_rate(document: Any) -> Decimal:
    """Gespeicherter Steuersatz des Belegs in Prozent; bei Altbelegen ohne Satz abgeleitet."""
    stored = _field(document, "vat_rate", "tax_rate")
    if stored is not None:
        return Decimal(str(float(stored)))
    return legacy_vat_rate(invoice_positions(document), stored_gross=_field(document, "total_brutto"))


def _is_final_invoice(document: Any) -> bool:
    return bool(_field(document, "is_final_invoice"))


def belegsummen_for_document(document: Any, company: Any = None) -> Belegsummen:
    """Belegsummen eines Belegs beliebiger Form.

    Ohne ``company`` gilt eine bereits am Beleg hängende Firma. Eine Schlussrechnung
    behält ihren beim Anlegen festgehaltenen Satz, auch wenn die Firma danach
    Kleinunternehmer wird; ihre Abzüge kommen aus dem Snapshot. Sind diese
    beschädigt, wirft ``final_deductions`` einen ``ValueError`` mit deutscher Meldung.
    """
    if company is None:
        company = _field(document, "company") if isinstance(document, dict) else vars(document).get("company")
    final = _is_final_invoice(document)
    deductions = None
    if final:
        deductions = [
            Abschlag(id=row.id, nr=row.nr, date=row.date, net=row.net, tax=row.tax)
            for row in final_deductions(document)
        ]
    switched_off = _field(document, "ust_enabled") is False
    small_business = bool(getattr(company, "is_small_business", False)) and not final
    return belegsummen(
        invoice_positions(document),
        vat_rate=invoice_vat_rate(document),
        charges_vat=not (switched_off or small_business),
        deductions=deductions,
    )


def _company(invoice: Any, session: Optional[Session]) -> Any:
    if session is not None and getattr(invoice, "company_id", None):
        return session.get(Company, int(invoice.company_id))
    # Nur eine bereits geladene Firma; ein abgelöster Beleg lädt nichts nach.
    return vars(invoice).get("company")


def belegsummen_for_invoice(invoice: Any, session: Optional[Session] = None) -> Belegsummen:
    """Belegsummen eines gespeicherten Belegs; die Firma kommt aus der Datenbank."""
    return belegsummen_for_document(invoice, _company(invoice, session))
