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


def status_not_allowed_reason(document: Any, new_status: str) -> str | None:
    """Grund, warum `new_status` für dieses Dokument nicht setzbar ist, sonst None."""
    target = InvoiceStatus(new_status)
    if _is_quote(document):
        if target not in QUOTE_STATUSES:
            return "Dieser Status gilt nur für Rechnungen, nicht für Angebote"
    elif target in QUOTE_ONLY_STATUSES:
        return "Dieser Status gilt nur für Angebote, nicht für Rechnungen"
    return None


def is_accepted_quote(document: Any) -> bool:
    """Ein angenommenes Angebot ist nicht mehr änderbar (Kopf und Positionen)."""
    return _is_quote(document) and getattr(document, "status", None) == InvoiceStatus.ACCEPTED


def accepted_quote_status_reason(document: Any, new_status: str) -> str | None:
    """ACCEPTED ist für Angebote endgültig: kein Statuswechsel mehr hinaus.

    Der Status ACCEPTED selbst bleibt setzbar (idempotent). Der Aufrufer wertet
    einen Grund als Konflikt (409), nicht als ungültigen Status (400).
    """
    if not is_accepted_quote(document):
        return None
    if InvoiceStatus(new_status) == InvoiceStatus.ACCEPTED:
        return None
    return "Ein angenommenes Angebot ist endgültig; sein Status lässt sich nicht mehr ändern"
