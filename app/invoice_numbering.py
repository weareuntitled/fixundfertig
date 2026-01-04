from __future__ import annotations

import os
import re

from data import Company, Customer, Invoice


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return ""


def _sanitize_filename(value: str) -> str:
    cleaned = value.strip().replace(os.sep, "-")
    cleaned = re.sub(r"[^\w.\-]+", "_", cleaned, flags=re.UNICODE)
    return cleaned or "rechnung"


def derive_customer_code(customer: Customer | None) -> str:
    if customer and customer.short_code:
        code = customer.short_code.strip().upper()
        if code:
            return code
    base = ""
    if customer:
        base = (customer.name or customer.display_name or "").strip()
    base = re.sub(r"[^A-Za-z0-9]", "", base.upper())
    return base[:4] if base else "KUNDE"


def _format_template(template: str, values: dict) -> str:
    return template.format_map(_SafeDict(values))


def build_invoice_number(
    company: Company,
    customer: Customer | None,
    seq: int | str,
    date_str: str | None,
) -> str:
    template = (company.invoice_number_template or "{seq}").strip() or "{seq}"
    values = {
        "seq": seq,
        "date": date_str or "",
        "customer_code": derive_customer_code(customer),
        "customer_kdnr": customer.kdnr if customer else "",
    }
    return _format_template(template, values)


def build_invoice_filename(company: Company, invoice: Invoice, customer: Customer | None) -> str:
    template = (company.invoice_filename_template or "rechnung_{nr}").strip() or "rechnung_{nr}"
    raw_nr = str(invoice.nr) if invoice.nr is not None else ""
    try:
        seq = int(raw_nr)
    except (TypeError, ValueError):
        seq = ""
    values = {
        "nr": raw_nr,
        "seq": seq,
        "date": invoice.date or "",
        "customer_code": derive_customer_code(customer),
        "customer_kdnr": customer.kdnr if customer else "",
    }
    filename = _format_template(template, values)
    filename = _sanitize_filename(filename)
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return filename
