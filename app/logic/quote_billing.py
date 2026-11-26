"""Ein Abrechnungsweg pro Angebot (#495): welche Abrechnungsaktionen ein Angebot erlaubt.

Es gibt zwei Wege: Vollrechnung („In Rechnung umwandeln“) oder Abschläge plus genau
eine Schlussrechnung. Abrechnen geht nur aus „Gesendet“ oder „Angenommen“.

`quote_billing` ist die einzige Quelle der Regeln: der Server prüft damit jede
Abrechnung (Verstoß = `BillingConflict`, HTTP 409), und die Angebotsseite bekommt
dasselbe Ergebnis als Feld `billing` der Angebots-API, um gesperrte Aktionen als
Text mit Grund (und Link auf die sperrende Rechnung) statt als Knopf zu zeigen.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import update
from sqlmodel import Session, select

from data import DocumentType, Invoice, InvoiceStatus, NOT_ISSUED_STATUSES, is_issued_status
from services.payment_plan import parse_payment_plan

DRAFT_REASON = "Ein Entwurf lässt sich nicht abrechnen. Senden Sie das Angebot zuerst."
REJECTED_REASON = "Ein abgelehntes Angebot lässt sich nicht abrechnen."


class BillingConflict(Exception):
    """Die Abrechnung verstößt gegen den Abrechnungsweg des Angebots (HTTP 409)."""


@dataclass(frozen=True)
class BillingAction:
    """Ob eine Abrechnungsaktion erlaubt ist; sonst der Grund und ggf. die sperrende Rechnung."""

    allowed: bool = True
    reason: str = ""
    invoice_id: int | None = None
    invoice_nr: str | None = None

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "invoice_id": self.invoice_id,
            "invoice_nr": self.invoice_nr,
        }


@dataclass(frozen=True)
class QuoteBilling:
    """Die erlaubten Abrechnungsaktionen eines Angebots."""

    convert: BillingAction = field(default_factory=BillingAction)
    down_payment: BillingAction = field(default_factory=BillingAction)
    final_invoice: BillingAction = field(default_factory=BillingAction)
    # Gesendet, noch nicht angenommen: das erste Abrechnen nimmt das Angebot an.
    # Die Oberfläche fragt vorher nach.
    requires_acceptance: bool = False

    def as_dict(self) -> dict:
        return {
            "convert": self.convert.as_dict(),
            "down_payment": self.down_payment.as_dict(),
            "final_invoice": self.final_invoice.as_dict(),
            "requires_acceptance": self.requires_acceptance,
        }


@dataclass(frozen=True)
class QuoteSettlement:
    """Wie viel vom Angebot ist schon abgerechnet (#499).

    Grundlage sind die gestellten Rechnungen zum Angebot: nicht storniert und nicht
    im Entwurf. Der Zahlungsplan zählt nicht — er ist der Plan, nicht die Rechnung.
    """

    billed_brutto: float = 0.0
    total_brutto: float = 0.0
    open_brutto: float = 0.0
    billed_count: int = 0

    def as_dict(self) -> dict:
        return {
            "billed_brutto": self.billed_brutto,
            "total_brutto": self.total_brutto,
            "open_brutto": self.open_brutto,
            "billed_count": self.billed_count,
        }


def issued_invoices(session: Session, quote_id: int) -> list[Invoice]:
    """Gestellte Rechnungen zum Angebot, älteste zuerst.

    „Gestellt“ heißt: weder Entwurf noch storniert (`NOT_ISSUED_STATUSES`). Dieselbe
    Regel wie beim Abzug der Abschlagsrechnungen (`logic.final_invoice`).
    """
    statement = (
        select(Invoice)
        .where(
            Invoice.quote_id == int(quote_id),
            Invoice.document_type == DocumentType.INVOICE,
            Invoice.status.notin_(list(NOT_ISSUED_STATUSES)),
        )
        .order_by(Invoice.id)
    )
    return list(session.exec(statement).all())


def quote_settlement(session: Session, quote: Invoice) -> QuoteSettlement:
    """Abrechnungsstand eines Angebots: abgerechnet, Angebot gesamt, offen.

    Die Summe ist der Bruttobetrag der gestellten Rechnungen zum Angebot (Abschläge
    und gegebenenfalls eine Vollrechnung), verglichen mit dem Bruttobetrag des
    Angebots. Was gestellt ist, zählt; was im Entwurf liegt, zählt nicht mit.
    """
    total = round(float(quote.total_brutto or 0.0), 2)
    invoices = issued_invoices(session, int(quote.id))
    billed = round(sum(float(inv.total_brutto or 0.0) for inv in invoices), 2)
    return QuoteSettlement(
        billed_brutto=billed,
        total_brutto=total,
        open_brutto=round(max(total - billed, 0.0), 2),
        billed_count=len(invoices),
    )


def _blocked(reason: str, invoice: Invoice | None = None) -> BillingAction:
    return BillingAction(
        allowed=False,
        reason=reason,
        invoice_id=int(invoice.id) if invoice is not None and invoice.id else None,
        invoice_nr=str(invoice.nr) if invoice is not None and invoice.nr else None,
    )


def quote_billing(session: Session, quote: Invoice) -> QuoteBilling:
    """Erlaubte Abrechnungsaktionen eines Angebots nach Status und vorhandenen Rechnungen."""
    status = quote.status
    if status == InvoiceStatus.DRAFT:
        blocked = _blocked(DRAFT_REASON)
        return QuoteBilling(convert=blocked, down_payment=blocked, final_invoice=blocked)
    if status == InvoiceStatus.REJECTED:
        blocked = _blocked(REJECTED_REASON)
        return QuoteBilling(convert=blocked, down_payment=blocked, final_invoice=blocked)

    active = session.exec(
        select(Invoice)
        .where(
            Invoice.quote_id == int(quote.id),
            Invoice.document_type == DocumentType.INVOICE,
            Invoice.status != InvoiceStatus.CANCELLED,
        )
        .order_by(Invoice.id)
    ).all()
    finals = [inv for inv in active if inv.is_final_invoice]
    downs = [inv for inv in active if inv.down_payment_index is not None]
    fulls = [inv for inv in active if inv.down_payment_index is None and not inv.is_final_invoice]

    if fulls:
        full = fulls[0]
        done = _blocked(f"Das Angebot ist mit Rechnung {full.nr} vollständig abgerechnet.", full)
        return QuoteBilling(
            convert=_blocked(f"Das Angebot ist bereits in Rechnung {full.nr} umgewandelt.", full),
            down_payment=done,
            final_invoice=done,
        )

    if finals:
        final = finals[0]
        convert = _blocked(f"Die Schlussrechnung {final.nr} rechnet das Angebot bereits ab.", final)
        down_payment = _blocked(f"Die Schlussrechnung {final.nr} rechnet den Rest bereits ab.", final)
        final_invoice = _blocked(
            f"Zu diesem Angebot gibt es bereits eine Schlussrechnung (Rechnung {final.nr}). "
            "Stornieren Sie sie, um eine neue zu erzeugen.",
            final,
        )
    else:
        convert = (
            _blocked(
                f"Es gibt bereits eine Abschlagsrechnung ({downs[0].nr}). "
                "Rechnen Sie den Rest mit der Schlussrechnung ab.",
                downs[0],
            )
            if downs
            else BillingAction()
        )
        down_payment = (
            BillingAction()
            if parse_payment_plan(quote.payment_plan)
            else _blocked("Das Angebot hat keinen Zahlungsplan.")
        )
        issued = [inv for inv in downs if is_issued_status(inv.status)]
        drafts = [inv for inv in downs if inv.status == InvoiceStatus.DRAFT]
        if drafts:
            final_invoice = _blocked(
                f"Stellen oder stornieren Sie zuerst die Abschlagsrechnung {drafts[0].nr}; ein Entwurf zählt nicht.",
                drafts[0],
            )
        elif issued:
            final_invoice = BillingAction()
        else:
            final_invoice = _blocked(
                "Eine Schlussrechnung entsteht nur mit einer gestellten Abschlagsrechnung."
            )

    return QuoteBilling(
        convert=convert,
        down_payment=down_payment,
        final_invoice=final_invoice,
        requires_acceptance=status != InvoiceStatus.ACCEPTED,
    )


def lock_quote_for_billing(session: Session, quote: Invoice) -> None:
    """Schreibsperre auf die Angebotszeile, bevor die Regeln geprüft werden.

    Ein (wirkungsloses) UPDATE sperrt die Zeile bis zum Commit: in PostgreSQL die
    Zeile, in SQLite die Datenbank. Eine gleichzeitige zweite Abrechnung wartet
    und sieht danach die erste Rechnung; sie erzeugt kein zweites Dokument.
    """
    session.exec(  # type: ignore[call-overload]
        update(Invoice).where(Invoice.id == int(quote.id)).values(revision_nr=Invoice.revision_nr)
    )
    session.refresh(quote)


def ensure_billable(session: Session, quote: Invoice, action: str) -> None:
    """Sperrt das Angebot und wirft `BillingConflict`, wenn `action` nicht erlaubt ist.

    `action` ist "convert", "down_payment" oder "final_invoice".
    """
    if quote.document_type != DocumentType.QUOTE:
        return
    lock_quote_for_billing(session, quote)
    result: BillingAction = getattr(quote_billing(session, quote), action)
    if not result.allowed:
        session.rollback()
        raise BillingConflict(result.reason)
