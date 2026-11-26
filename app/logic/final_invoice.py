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

    def as_dict(self) -> dict:
        return {"id": self.id, "nr": self.nr, "net": self.net, "tax": self.tax, "total": self.total}


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
            )
        )
    return rows


def deduction_totals(rows: list[DownPaymentDeduction]) -> tuple[float, float]:
    """Summe Netto und Summe Steuer aller Abzüge."""
    return (
        round(sum(row.net for row in rows), 2),
        round(sum(row.tax for row in rows), 2),
    )


def final_invoice_totals(net: float, vat_percent: float, rows: list[DownPaymentDeduction]) -> dict:
    """Gesamtleistung, Abschläge und Restbetrag einer Schlussrechnung.

    ``net`` sind die Netto-Positionen der Schlussrechnung. Die Steuer der
    Gesamtleistung entsteht mit dem Steuersatz des Dokuments (0 bei
    Kleinunternehmern). Der Restbetrag ist Gesamtleistung minus Abschläge.
    """
    net = round(float(net or 0), 2)
    rate = float(vat_percent or 0)
    tax = round(net * rate / 100.0, 2) if rate > 0 else 0.0
    gross = round(net + tax, 2)
    sum_net, sum_tax = deduction_totals(rows)
    sum_gross = round(sum_net + sum_tax, 2)
    return {
        "net": net,
        "tax": tax,
        "gross": gross,
        "sum_net": sum_net,
        "sum_tax": sum_tax,
        "sum_gross": sum_gross,
        "rest_net": round(net - sum_net, 2),
        "rest_tax": round(tax - sum_tax, 2),
        "rest": round(gross - sum_gross, 2),
    }
