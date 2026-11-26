"""Der Einleitungstext im Formular muss der des PDFs entsprechen (#499).

Das Formular nennt den Standardtext, den das PDF ohne eigenen Text druckt: beim Angebot
`QUOTE_INTRO`, bei der Rechnung `INVOICE_INTRO` (`app/services/invoice_pdf_draw.py`).
Der Frontend-Spiegel (`frontend/src/lib/document-intro.ts`) darf nicht davonlaufen.
"""
from __future__ import annotations

from pathlib import Path

from app.services.invoice_pdf_draw import INVOICE_INTRO, QUOTE_INTRO

FRONTEND_FILE = Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib" / "document-intro.ts"


def _frontend_source() -> str:
    assert FRONTEND_FILE.exists(), f"{FRONTEND_FILE} fehlt"
    return FRONTEND_FILE.read_text(encoding="utf-8")


def test_the_form_mirrors_the_quote_intro() -> None:
    assert QUOTE_INTRO in _frontend_source()


def test_the_form_mirrors_the_invoice_intro() -> None:
    assert INVOICE_INTRO in _frontend_source()
