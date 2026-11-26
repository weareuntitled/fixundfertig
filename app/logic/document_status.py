"""Welche Status eine Dokumentart tragen darf, und wann ein Angebot gesperrt ist.

Angebote und Rechnungen teilen sich die Spalte `invoice.status` (Enum `InvoiceStatus`).
Ein Angebot kennt nur Entwurf, Gesendet, Angenommen und Abgelehnt. „Abgelaufen“ wird
nie gespeichert: es ist ein gesendetes Angebot, dessen „gültig bis“ vorbei ist (Anzeige
im Frontend, `quoteDisplayStatus`). Die Rechnungsstatus bleiben unverändert; nur die
beiden Angebotsstatus sind für Rechnungen nicht setzbar.
"""
from __future__ import annotations

from typing import Any

from data import DocumentType, InvoiceStatus

QUOTE_STATUSES = frozenset(
    {InvoiceStatus.DRAFT, InvoiceStatus.SENT, InvoiceStatus.ACCEPTED, InvoiceStatus.REJECTED}
)
QUOTE_ONLY_STATUSES = frozenset({InvoiceStatus.ACCEPTED, InvoiceStatus.REJECTED})


def _is_quote(document: Any) -> bool:
    return getattr(document, "document_type", DocumentType.INVOICE) == DocumentType.QUOTE


def status_not_allowed_reason_for_type(document_type: Any, new_status: str) -> str | None:
    """Grund, warum `new_status` für diese Dokumentart nicht setzbar ist, sonst None."""
    target = InvoiceStatus(new_status)
    if DocumentType(document_type) == DocumentType.QUOTE:
        if target not in QUOTE_STATUSES:
            return "Dieser Status gilt nur für Rechnungen, nicht für Angebote"
    elif target in QUOTE_ONLY_STATUSES:
        return "Dieser Status gilt nur für Angebote, nicht für Rechnungen"
    return None


def status_not_allowed_reason(document: Any, new_status: str) -> str | None:
    """Grund, warum `new_status` für dieses Dokument nicht setzbar ist, sonst None."""
    return status_not_allowed_reason_for_type(
        getattr(document, "document_type", DocumentType.INVOICE), new_status
    )


def creation_status_reason(document_type: Any, new_status: str) -> str | None:
    """Grund, warum ein Dokument nicht mit diesem Status angelegt werden darf, sonst None.

    Ein Angebot entsteht immer im Entwurf: „Gesendet“ gibt es nur durch den Versand,
    „Angenommen“ und „Abgelehnt“ erst durch die Entscheidung am Angebot. Eine Rechnung
    darf keinen Angebotsstatus bekommen.
    """
    doc_type = DocumentType(document_type)
    target = InvoiceStatus(new_status)
    if doc_type == DocumentType.QUOTE:
        if target != InvoiceStatus.DRAFT:
            return "Ein Angebot wird im Entwurf angelegt; „Gesendet“ entsteht durch den Versand"
        return None
    return status_not_allowed_reason_for_type(doc_type, target)


def is_accepted_quote(document: Any) -> bool:
    """Ein angenommenes Angebot ist nicht mehr änderbar (Kopf und Positionen)."""
    return _is_quote(document) and getattr(document, "status", None) == InvoiceStatus.ACCEPTED


def is_rejected_quote(document: Any) -> bool:
    """Ein abgelehntes Angebot ist nur noch lesbar (Kopf und Positionen)."""
    return _is_quote(document) and getattr(document, "status", None) == InvoiceStatus.REJECTED


def accepted_quote_status_reason(document: Any, new_status: str) -> str | None:
    """ACCEPTED ist für Angebote endgültig: kein Statuswechsel mehr hinaus.

    Der Status ACCEPTED selbst bleibt setzbar (idempotent). Ebenso „Gesendet“: das ist
    das Zurücksetzen einer Entscheidung und wird in `logic.quote_decision` geprüft
    (zurücknehmen geht, solange das Angebot keine Rechnung hat).

    Der Aufrufer wertet einen Grund als Konflikt (409), nicht als ungültigen Status (400).
    """
    if not is_accepted_quote(document):
        return None
    if InvoiceStatus(new_status) in (InvoiceStatus.ACCEPTED, InvoiceStatus.SENT):
        return None
    return "Ein angenommenes Angebot ist endgültig; sein Status lässt sich nicht mehr ändern"
