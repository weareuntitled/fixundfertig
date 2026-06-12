from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

from renderer import PDFInvoiceRenderer
from invoice_numbering import build_invoice_filename, build_invoice_number
from .invoice_utils import build_invoice_preview_html, compute_invoice_totals


def _get(obj: Any, *names: str, default: Any = "") -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        for n in names:
            if n in obj and obj[n] not in (None, ""):
                return obj[n]
        return default
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v not in (None, ""):
                return v
    return default


def build_preview_invoice(
    comp, customer_obj, items: list[dict], title: str, invoice_date: str,
    service_from: str, service_to: str, intro_text: str, vat_enabled: bool,
) -> dict:
    vat_rate = max((float(_get(it, "tax_rate", default=0) or 0) for it in items), default=0.0)
    net, vat, gross = compute_invoice_totals(items, vat_enabled, vat_rate)

    seq = getattr(comp, "next_invoice_nr", None)
    try:
        preview_number = build_invoice_number(comp, customer_obj, seq, invoice_date)
    except Exception:
        preview_number = f"INV-{invoice_date}" if invoice_date else "ENTWURF"

    try:
        preview_ns = SimpleNamespace(nr=preview_number, date=invoice_date)
        preview_filename = build_invoice_filename(comp, preview_ns, customer_obj)
    except Exception:
        preview_filename = ""

    return {
        "title": title or "Rechnung",
        "invoice_number": preview_number,
        "invoice_date": invoice_date,
        "filename": preview_filename,
        "service_from": service_from,
        "service_to": service_to,
        "intro_text": intro_text,
        "company": comp,
        "customer": customer_obj,
        "items": items,
        "show_tax": vat_enabled,
        "tax_rate": vat_rate,
        "kleinunternehmer_note": "Als Kleinunternehmer im Sinne von § 19 UStG wird keine Umsatzsteuer berechnet.",
        "totals": {"net": net, "vat": vat, "gross": gross},
    }


def render_preview_html(invoice: dict) -> str:
    return build_invoice_preview_html(invoice)


def render_preview_pdf_frame(invoice: dict, renderer: PDFInvoiceRenderer) -> str:
    pdf_bytes = renderer.render(invoice, template_id=None)
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return (
        "<div class=\"ff-invoice-preview-frame\">"
        "<iframe "
        f"src=\"data:application/pdf;base64,{pdf_b64}\" "
        "title=\"Invoice preview\"></iframe>"
        "</div>"
    )
