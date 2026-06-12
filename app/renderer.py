from __future__ import annotations

import base64
from typing import Any

from renderer_interface import InvoiceRenderer
from services.invoice_pdf import render_invoice_to_pdf_bytes as _render_reportlab


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


def _looks_like_invoice(x: Any) -> bool:
    if x is None:
        return False
    keys = ("items", "positions", "customer", "title", "invoice_date")
    if isinstance(x, dict):
        return any(k in x for k in keys)
    return any(hasattr(x, k) for k in keys)


def _looks_like_company(x: Any) -> bool:
    if x is None:
        return False
    keys = ("iban", "tax_id", "vat_id", "street", "zip", "city", "name")
    if isinstance(x, dict):
        return any(k in x for k in keys)
    return any(hasattr(x, k) for k in keys)


def _extract_company_customer(invoice: Any) -> tuple[Any, Any]:
    if isinstance(invoice, dict):
        return invoice.get("company"), invoice.get("customer")
    return getattr(invoice, "company", None), getattr(invoice, "customer", None)


class PDFInvoiceRenderer(InvoiceRenderer):
    def render(self, invoice: Any, template_id: str | None = None) -> bytes:
        company, customer = _extract_company_customer(invoice)
        return _render_reportlab(invoice, company=company, customer=customer)


def render_invoice_pdf_bytes(invoice: Any, company: Any) -> bytes:
    return _render_reportlab(invoice, company=company)


def render_invoice_pdf_base64(invoice: Any, company: Any) -> str:
    return base64.b64encode(render_invoice_pdf_bytes(invoice, company)).decode("ascii")


def render_invoice_to_pdf_bytes(*args, **kwargs) -> bytes:
    """Kompatibles Wrapper — akzeptiert (invoice, company) oder Keyword-Args."""
    if "invoice" in kwargs or "company" in kwargs or "customer" in kwargs:
        return _render_reportlab(
            kwargs.get("invoice"),
            company=kwargs.get("company"),
            customer=kwargs.get("customer"),
        )
    if len(args) >= 2:
        a, b = args[0], args[1]
        if _looks_like_invoice(a) and _looks_like_company(b):
            return _render_reportlab(a, company=b)
        if _looks_like_company(a) and _looks_like_invoice(b):
            return _render_reportlab(b, company=a)
        return _render_reportlab(a, company=b)
    if len(args) == 1:
        invoice = args[0]
        company, customer = _extract_company_customer(invoice)
        return _render_reportlab(invoice, company=company, customer=customer)
    raise TypeError("render_invoice_to_pdf_bytes needs at least (invoice, company)")


def render_invoice_to_pdf_base64(*args, **kwargs) -> str:
    return base64.b64encode(render_invoice_to_pdf_bytes(*args, **kwargs)).decode("ascii")
