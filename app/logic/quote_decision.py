"""Entscheidungen am Angebot (#497): „Gesendet“ ohne Mailserver, Zurücksetzen, Gültigkeit.

Drei Regeln, eine Quelle:

- „Als gesendet markieren“: Entwurf → Gesendet. Wer das PDF selbst verschickt, braucht
  keinen Mailserver; danach greift „Abgelaufen“ (Gesendet + „gültig bis“ in der Vergangenheit).
- „Zurücksetzen“: eine Entscheidung (angenommen oder abgelehnt) → Gesendet, solange das
  Angebot keine Rechnung hat. Mit Rechnung ist die Entscheidung endgültig (409).
- „Gültigkeit verlängern“: „gültig bis“ = heute + 30 Tage. Das Angebot bekommt eine frische
  Frist ab heute, nicht 30 Tage nach dem alten Ablaufdatum — sonst bliebe nur ein paar
  Tage Restfrist, und der Kunde müsste binnen weniger Tage entscheiden.

Die Regeln stehen hier, damit Server (`/api/invoices`) und Oberfläche dasselbe sagen.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from data import DocumentType, Invoice, InvoiceStatus

EXTENDED_VALIDITY_DAYS = 30


def is_quote(quote: Invoice) -> bool:
    """Ist das Dokument ein Angebot?"""
    return getattr(quote, "document_type", DocumentType.INVOICE) == DocumentType.QUOTE


def quote_has_invoices(session: Session, quote: Invoice) -> bool:
    """Hat das Angebot schon eine Rechnung? Stornierte Rechnungen zählen nicht mit.

    Eine stornierte Rechnung gibt den Abrechnungsweg frei (#495); sie darf eine
    Entscheidung nicht festschreiben.
    """
    if not is_quote(quote):
        return False
    found = session.exec(
        select(Invoice).where(
            Invoice.quote_id == int(quote.id),
            Invoice.document_type == DocumentType.INVOICE,
            Invoice.status != InvoiceStatus.CANCELLED,
        )
    ).first()
    return found is not None


def mark_sent_reason(quote: Invoice, has_invoices: bool) -> str | None:
    """Grund, warum das Angebot nicht auf „Gesendet“ gesetzt werden kann; sonst None.

    Entwurf → Gesendet geht immer (ohne Mailserver). Aus „Angenommen“ oder „Abgelehnt“
    geht es nur zurück, solange das Angebot keine Rechnung hat.
    """
    if not is_quote(quote):
        return "Nur Angebote können als gesendet markiert werden"
    status = quote.status
    if status in (InvoiceStatus.DRAFT, InvoiceStatus.SENT):
        return None
    if status in (InvoiceStatus.ACCEPTED, InvoiceStatus.REJECTED):
        if has_invoices:
            return (
                "Zu diesem Angebot gibt es schon eine Rechnung; "
                "die Entscheidung lässt sich nicht mehr zurücknehmen."
            )
        return None
    return "Dieser Status lässt sich nicht in „Gesendet“ ändern"


def decision_reset_reason(quote: Invoice, new_status: str, has_invoices: bool) -> str | None:
    """Grund, warum eine Entscheidung nicht auf „Gesendet“ zurückgesetzt werden kann.

    Das Zurücksetzen gilt für „Angenommen“ und „Abgelehnt“ und nur, solange das Angebot
    keine Rechnung hat. Für alle anderen Statuswechsel ist die Antwort None.
    """
    if not is_quote(quote):
        return None
    if InvoiceStatus(new_status) != InvoiceStatus.SENT:
        return None
    if quote.status not in (InvoiceStatus.ACCEPTED, InvoiceStatus.REJECTED):
        return None
    return mark_sent_reason(quote, has_invoices)


def validity_extension_reason(quote: Invoice) -> str | None:
    """Grund, warum die Gültigkeit nicht verlängert werden kann; sonst None.

    Angenommene Angebote sind endgültig, abgelehnte nur lesbar: bei beiden bleibt das
    „gültig bis“ stehen.
    """
    if not is_quote(quote):
        return "Nur Angebote haben eine Gültigkeit"
    if quote.status == InvoiceStatus.ACCEPTED:
        return (
            "Ein angenommenes Angebot ist endgültig; "
            "seine Gültigkeit lässt sich nicht mehr ändern."
        )
    if quote.status == InvoiceStatus.REJECTED:
        return "Ein abgelehntes Angebot lässt sich nicht mehr ändern"
    return None


def extended_valid_until(today: date | None = None) -> str:
    """Neues „gültig bis“: 30 Tage ab heute."""
    start = today or date.today()
    return (start + timedelta(days=EXTENDED_VALIDITY_DAYS)).isoformat()
