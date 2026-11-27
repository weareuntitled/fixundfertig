"""Schlussrechnung (#491): gestellte Abschlagsrechnungen von der Gesamtleistung abziehen.

„Gestellt“ heißt: die Abschlagsrechnung ist weder im Entwurf noch storniert
(`is_issued_status`). Diese eine Regel gilt für die Voraussetzung der Schlussrechnung
(„nur mit einer gestellten Abschlagsrechnung“) und für den Abzug (was abgezogen wird) —
beide lesen dieselbe Liste `issued_down_payments`. Abgezogen werden die tatsächlich
gestellten Abschlagsrechnungen des Angebots, nicht die Prozentwerte des Zahlungsplans.
Netto und Steuer werden getrennt geführt; die Steuer einer Abschlagsrechnung ist ihr
Bruttobetrag minus ihre Netto-Positionen (bei Kleinunternehmern damit 0).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import math

from sqlmodel import Session, select

from data import DocumentType, Invoice, NOT_ISSUED_STATUSES


@dataclass(frozen=True)
class DownPaymentDeduction:
    """Eine abzuziehende Abschlagsrechnung mit getrenntem Netto und Steuer."""

    id: int
    nr: str
    net: float
    tax: float
    total: float
    # Rechnungsdatum (ISO), damit PDF, Mail und App „vom [Datum]“ nennen können.
    date: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id, "nr": self.nr, "date": self.date,
            "net": self.net, "tax": self.tax, "total": self.total,
        }


def final_deductions(invoice: Invoice | dict) -> list[DownPaymentDeduction]:
    """Read the immutable snapshot; missing or damaged historical data is never guessed."""
    try:
        snapshot = (invoice.get("final_deductions_json") if isinstance(invoice, dict)
                    else getattr(invoice, "final_deductions_json", None))
        raw = json.loads(snapshot)
        if not isinstance(raw, list):
            raise ValueError("invalid snapshot")
        rows = [DownPaymentDeduction(**row) for row in raw]
        for row in rows:
            if (type(row.id) is not int or row.id <= 0 or not isinstance(row.nr, str) or not row.nr.strip()
                or not isinstance(row.date, str)
                or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                       for value in (row.net, row.tax, row.total))
                or round(row.net + row.tax, 2) != round(row.total, 2)):
                raise ValueError("invalid deduction")
            date.fromisoformat(row.date)
        return rows
    except (AttributeError, TypeError, ValueError, KeyError) as exc:
        raise ValueError("Die Abzüge dieser Schlussrechnung sind nicht verlässlich gespeichert. Bitte prüfen; eine Neuberechnung, PDF-Neuerstellung oder E-Mail ist bis dahin gesperrt.") from exc


def invoice_net(invoice: Invoice) -> float:
    """Netto aus den Positionen eines Dokuments, auf Cent gerundet."""
    from logic.invoice import invoice_net_total

    return invoice_net_total(invoice)


def issued_down_payments(session: Session, quote_id: int) -> list[DownPaymentDeduction]:
    """Gestellte, nicht stornierte Abschlagsrechnungen eines Angebots, älteste zuerst.

    Die Liste ist die einzige Quelle der Wahrheit: sie beantwortet zugleich die
    Frage „darf es eine Schlussrechnung geben?“ (nicht leer) und „was wird abgezogen?“.
    """
    statement = (
        select(Invoice)
        .where(
            Invoice.quote_id == int(quote_id),
            Invoice.document_type == DocumentType.INVOICE,
            Invoice.down_payment_index.is_not(None),
            Invoice.status.notin_(list(NOT_ISSUED_STATUSES)),
        )
        .order_by(Invoice.id)
    )
    rows: list[DownPaymentDeduction] = []
    for invoice in session.exec(statement).all():
        net = invoice_net(invoice)
        total = round(float(invoice.total_brutto or 0), 2)
        rows.append(
            DownPaymentDeduction(
                id=int(invoice.id or 0),
                nr=str(invoice.nr or ""),
                net=net,
                tax=round(max(total - net, 0.0), 2),
                total=total,
                date=str(invoice.date or ""),
            )
        )
    return rows
