"""Pure document utility functions extracted from pages/documents.py."""
from __future__ import annotations

import json
import os
from datetime import datetime

from styles import C_BADGE_GRAY, C_BADGE_YELLOW


def doc_created_at(doc) -> datetime:
    created_at = doc.created_at
    if isinstance(created_at, datetime):
        return created_at
    try:
        return datetime.fromisoformat(str(created_at))
    except Exception:
        return datetime.min


def document_invoice_date(doc) -> str:
    value = getattr(doc, "invoice_date", None)
    return value or ""


def document_display_date(doc) -> str:
    doc_date = (getattr(doc, "doc_date", None) or "").strip()
    invoice_date = document_invoice_date(doc).strip()
    if doc_date:
        return doc_date
    if invoice_date:
        return invoice_date
    created_at = doc_created_at(doc)
    if created_at != datetime.min:
        return created_at.strftime("%Y-%m-%d")
    return ""


def document_accounting_year(doc) -> str:
    for candidate in (
        (getattr(doc, "doc_date", None) or "").strip(),
        document_invoice_date(doc).strip(),
    ):
        if candidate and len(candidate) >= 4 and candidate[:4].isdigit():
            return candidate[:4]
    return ""


def parse_keywords(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        value = str(value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = value
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    if isinstance(parsed, str):
        return [piece.strip() for piece in parsed.split(",") if piece.strip()]
    return [str(parsed).strip()] if str(parsed).strip() else []


def format_keywords(value: str | None) -> str:
    items = parse_keywords(value or "")
    return ", ".join(items) if items else "-"


def matches_query(doc, meta_values: dict[str, object], query: str) -> bool:
    if not query:
        return True
    terms = [term for term in query.lower().split() if term]
    if not terms:
        return True
    haystack_parts = [
        doc.original_filename,
        doc.title,
        doc.filename,
        doc.vendor,
        doc.doc_type,
        doc.document_type,
        doc.source,
        doc.doc_date,
        document_invoice_date(doc),
        document_display_date(doc),
        format_keywords(doc.keywords_json),
        meta_values.get("vendor"),
        meta_values.get("keywords"),
        meta_values.get("invoice_number"),
        meta_values.get("summary"),
        meta_values.get("amount_total"),
        meta_values.get("amount_net"),
        meta_values.get("amount_tax"),
    ]
    haystack = " ".join(
        str(part).lower() for part in haystack_parts if part is not None and str(part).strip()
    )
    return all(term in haystack for term in terms)


def coerce_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def vat_from_gross(amount_total: float, rate: float = 0.19) -> float:
    if amount_total <= 0 or rate <= 0:
        return 0.0
    return amount_total * (rate / (1 + rate))


def resolve_amounts(doc) -> tuple[float | None, float | None, float | None]:
    amount_total = coerce_float(doc.amount_total)
    amount_net = coerce_float(doc.amount_net)
    amount_tax = coerce_float(doc.amount_tax)
    if amount_total is None:
        amount_total = coerce_float(getattr(doc, "gross_amount", None))
    if amount_net is None:
        amount_net = coerce_float(getattr(doc, "net_amount", None))
    if amount_tax is None:
        amount_tax = coerce_float(getattr(doc, "tax_amount", None))
    if amount_tax is None and amount_total is not None and amount_net is not None:
        amount_tax = max(amount_total - amount_net, 0.0)
    if amount_tax is None and amount_total is not None and amount_net is None:
        amount_tax = vat_from_gross(amount_total)
    return amount_total, amount_net, amount_tax


def format_json(value: str | None, *, redact_payload: bool = False) -> str:
    if not value:
        return ""
    try:
        parsed = json.loads(value)
    except Exception:
        return str(value)
    if redact_payload and isinstance(parsed, dict):
        for key in ("file_bytes", "file_base64", "content_base64", "data_base64", "raw_base64"):
            if key in parsed:
                parsed[key] = "<redacted>"
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "-"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_amount_value(amount: float | None, currency: str | None) -> str:
    if amount is None:
        return "n/a"
    currency = (currency or "").strip()
    if currency:
        return f"{amount:,.2f} {currency}"
    return f"{amount:,.2f}"


def format_amount_eur(amount: float) -> str:
    return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def format_source(source: str | None) -> str:
    value = (source or "").strip().lower()
    if value in {"manual", "manuell"}:
        return "Manuell"
    if value == "n8n":
        return "n8n"
    if value in {"mail", "email"}:
        return "Mail"
    if value:
        return value.upper()
    return "-"


def resolve_status(doc, amount_total: float | None, vendor: str | None) -> tuple[str, str]:
    if amount_total is not None or (vendor or "").strip():
        return "Verarbeitet", C_BADGE_GRAY
    if (doc.source or "").strip().lower() in {"mail", "email"}:
        return "Eingang", C_BADGE_GRAY
    return "Neu", C_BADGE_YELLOW


def resolve_file_icon(mime: str, filename: str) -> tuple[str, str]:
    from styles import STYLE_BADGE_FILE_IMAGE, STYLE_BADGE_FILE_OTHER, STYLE_BADGE_FILE_PDF

    lower_mime = (mime or "").lower()
    lower_name = (filename or "").lower()
    if "pdf" in lower_mime or lower_name.endswith(".pdf"):
        return "picture_as_pdf", STYLE_BADGE_FILE_PDF
    if lower_mime.startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg")):
        return "image", STYLE_BADGE_FILE_IMAGE
    return "insert_drive_file", STYLE_BADGE_FILE_OTHER


def safe_export_filename(name: str) -> str:
    cleaned = (name or "").strip() or "document"
    cleaned = os.path.basename(cleaned)
    cleaned = cleaned.replace("/", "_").replace("\\", "_").replace(":", "_")
    return cleaned or "document"


def year_options(items) -> dict[str, str]:
    years: set[str] = set()
    for doc in items:
        doc_year = document_accounting_year(doc)
        if doc_year:
            years.add(doc_year)
    if not years:
        years = {str(datetime.now().year)}
    return {year: year for year in sorted(years, reverse=True)}
