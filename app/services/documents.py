from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException

from data import Document, DocumentMeta
from models.document import DocumentSource, safe_filename as model_safe_filename
from services.blob_storage import blob_storage
from services.storage import company_document_dir, company_documents_dir, ensure_company_dirs
from sqlmodel import Session, select

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
_DEFAULT_MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024
try:
    MAX_DOCUMENT_SIZE_BYTES = int(os.getenv("FF_MAX_UPLOAD_BYTES") or _DEFAULT_MAX_DOCUMENT_SIZE_BYTES)
except ValueError:
    MAX_DOCUMENT_SIZE_BYTES = _DEFAULT_MAX_DOCUMENT_SIZE_BYTES


def _storage_key_from_filename(filename: str) -> str:
    safe_name = safe_filename(os.path.basename(filename or "document"))
    root, ext = os.path.splitext(safe_name)
    token = secrets.token_hex(4)
    if not root:
        root = "document"
    return f"{root}-{token}{ext}"


def _extension(value: str) -> str:
    return Path(value).suffix.lower().lstrip(".")


def _parse_iso_date(value: str | None) -> datetime:
    try:
        return datetime.fromisoformat(value or "")
    except Exception:
        return datetime.min


def _document_filter_date(document: Document) -> datetime:
    for candidate in (
        (getattr(document, "doc_date", None) or "").strip(),
        (getattr(document, "invoice_date", None) or "").strip(),
    ):
        parsed = _parse_iso_date(candidate)
        if parsed != datetime.min:
            return parsed
    created_at = document.created_at
    if isinstance(created_at, datetime):
        return created_at
    return _parse_iso_date(str(created_at))


def normalize_keywords(value: Iterable[str] | str | None) -> str:
    if value is None:
        return "[]"
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "[]"
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            items = [piece.strip() for piece in re.split(r"[,;\n]+", raw) if piece.strip()]
            return json.dumps(_dedupe_keep_order(items), ensure_ascii=False)
        if isinstance(loaded, list):
            items = [str(item).strip() for item in loaded if str(item).strip()]
            return json.dumps(_dedupe_keep_order(items), ensure_ascii=False)
        return json.dumps([str(loaded).strip()], ensure_ascii=False)
    items = [str(item).strip() for item in value if str(item).strip()]
    return json.dumps(_dedupe_keep_order(items), ensure_ascii=False)


def safe_filename(value: str) -> str:
    return model_safe_filename(value)


def build_display_title(
    vendor: str | None,
    doc_date: str | None,
    amount_total: float | None,
    currency: str | None,
    fallback_filename: str | None,
) -> str:
    parts: list[str] = []
    if vendor:
        parts.append(str(vendor).strip())
    if doc_date:
        parts.append(str(doc_date).strip())
    if amount_total is not None:
        amount_str = f"{amount_total:.2f}"
        if currency:
            amount_str = f"{amount_str} {currency}"
        parts.append(amount_str)
    title = " - ".join([part for part in parts if part])
    if title:
        return title
    fallback = (fallback_filename or "").strip()
    if fallback:
        return os.path.splitext(os.path.basename(fallback))[0] or "Dokument"
    return "Dokument"


def build_download_filename(title: str | None, mime: str | None) -> str:
    base = safe_filename(title or "document")
    root, ext = os.path.splitext(base)
    mime_value = (mime or "").lower().strip()
    if mime_value in {"application/pdf", "application/x-pdf"} or mime_value.endswith("/pdf"):
        return f"{root or base}.pdf"
    return base if ext or root else "document"


def _dedupe_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def validate_document_upload(filename: str, size_bytes: int | None) -> None:
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type")
    if size_bytes is not None and size_bytes > MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large")


def compute_sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compute_sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_document_record(
    company_id: int,
    original_filename: str,
    *,
    mime_type: str = "",
    size_bytes: int = 0,
    sha256: str = "",
    source: DocumentSource | str = "",
    doc_type: str = "",
    storage_key: str | None = None,
    storage_path: str | None = None,
    title: str = "",
    description: str = "",
    vendor: str = "",
    doc_number: str = "",
    doc_date: str | None = None,
    amount_total: float | None = None,
    amount_net: float | None = None,
    amount_tax: float | None = None,
    currency: str | None = None,
    keywords_json: str | None = None,
) -> Document:
    storage_key = storage_key or ""
    source_value = source.value if isinstance(source, DocumentSource) else (source or "")
    return Document(
        company_id=company_id,
        filename=safe_filename(original_filename or "document"),
        original_filename=original_filename,
        storage_key=storage_key,
        storage_path=storage_path or "",
        mime=mime_type,
        mime_type=mime_type,
        size=int(size_bytes or 0),
        size_bytes=int(size_bytes or 0),
        sha256=sha256,
        source=source_value,
        doc_type=doc_type or _extension(original_filename or ""),
        title=title,
        description=description,
        vendor=vendor,
        doc_number=doc_number,
        doc_date=doc_date,
        amount_total=amount_total,
        amount_net=amount_net,
        amount_tax=amount_tax,
        currency=currency,
        keywords_json=keywords_json or "[]",
    )


def document_storage_path(company_id: int, storage_key: str) -> str:
    if not storage_key:
        return ""
    ensure_company_dirs(company_id)
    if os.path.isabs(storage_key) or storage_key.startswith("storage/"):
        return storage_key
    if storage_key.startswith("companies/") or storage_key.startswith("documents/"):
        root = (os.getenv("STORAGE_LOCAL_ROOT", "storage") or "storage").strip()
        return os.path.join(root, storage_key)
    return os.path.join(company_documents_dir(company_id), storage_key)


def ensure_document_dir(company_id: int, document_id: int | None = None) -> str:
    directory = (
        company_document_dir(company_id, document_id) if document_id is not None else company_documents_dir(company_id)
    )
    os.makedirs(directory, exist_ok=True)
    return directory


def resolve_document_path(storage_path: str | None) -> str:
    if not storage_path:
        return ""
    if os.path.isabs(storage_path):
        for marker in (f"{os.sep}companies{os.sep}", f"{os.sep}documents{os.sep}"):
            if marker in storage_path:
                storage_path = storage_path.split(marker, 1)[1]
                storage_path = f"{marker.strip(os.sep)}{os.sep}{storage_path}".lstrip(os.sep)
                break
        else:
            marker = f"{os.sep}storage{os.sep}"
            if marker in storage_path:
                storage_path = storage_path.split(marker, 1)[1]
            else:
                return storage_path
    if storage_path.startswith("storage/"):
        storage_path = storage_path.removeprefix("storage/").lstrip("/")
    if storage_path.startswith("companies/") or storage_path.startswith("documents/"):
        root = (os.getenv("STORAGE_LOCAL_ROOT", "storage") or "storage").strip()
        return os.path.join(root, storage_path)
    return storage_path


def set_document_storage_path(document: Document) -> None:
    if not document.storage_path and document.storage_key:
        document.storage_path = document.storage_key


def _coerce_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _coerce_payload_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        for key in ("value", "amount", "total", "gross", "net", "tax"):
            if key in value:
                return _coerce_payload_float(value.get(key))
        for nested_value in value.values():
            parsed = _coerce_payload_float(nested_value)
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        cleaned = re.sub(r"[^\d,.\-]", "", cleaned)
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        return _coerce_float(cleaned)
    return _coerce_float(value)


def _extract_meta_payload(meta: DocumentMeta | None) -> dict:
    if not meta or not meta.raw_payload_json:
        return {}
    try:
        payload = json.loads(meta.raw_payload_json)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_document_meta_values(meta: DocumentMeta | None) -> dict[str, object]:
    payload = _extract_meta_payload(meta)
    extracted = payload.get("extracted") if isinstance(payload.get("extracted"), dict) else {}
    source = extracted or payload
    if not source:
        return {}

    def _resolve_payload_amount(*keys: str) -> float | None:
        containers = [source, payload]
        nested_keys = ("amounts", "totals", "total", "amount")
        for container in containers:
            if not isinstance(container, dict):
                continue
            for key in keys:
                if key in container:
                    return _coerce_payload_float(container.get(key))
            for nested_key in nested_keys:
                nested = container.get(nested_key)
                if not isinstance(nested, dict):
                    continue
                for key in keys:
                    if key in nested:
                        return _coerce_payload_float(nested.get(key))
        return None

    def _resolve_payload_text(*keys: str) -> str:
        containers = [source, payload]
        nested_keys = ("amounts", "totals", "total", "amount")
        for container in containers:
            if not isinstance(container, dict):
                continue
            for key in keys:
                if key in container and container.get(key) is not None:
                    return str(container.get(key)).strip()
            for nested_key in nested_keys:
                nested = container.get(nested_key)
                if not isinstance(nested, dict):
                    continue
                for key in keys:
                    if key in nested and nested.get(key) is not None:
                        return str(nested.get(key)).strip()
        return ""

    size_value = (
        source.get("file_size")
        or source.get("size_bytes")
        or source.get("size")
        or payload.get("file_size")
        or payload.get("size_bytes")
        or payload.get("size")
    )
    amount_total = _resolve_payload_amount(
        "amount_total",
        "gross_amount",
        "amount_gross",
        "total_gross",
        "total_amount",
        "amount",
        "gross",
        "brutto",
        "amount_brutto",
    )
    amount_net = _resolve_payload_amount(
        "amount_net",
        "net_amount",
        "total_net",
        "net",
        "netto",
        "amount_netto",
    )
    amount_tax = _resolve_payload_amount(
        "amount_tax",
        "tax_amount",
        "amount_vat",
        "vat_amount",
        "total_tax",
        "tax",
        "vat",
        "ust",
        "steuer",
    )
    currency_value = _resolve_payload_text("currency", "currency_code", "currency_iso")
    return {
        "vendor": (source.get("vendor") or "").strip(),
        "doc_number": (source.get("doc_number") or "").strip(),
        "amount_total": amount_total,
        "amount_net": amount_net,
        "amount_tax": amount_tax,
        "currency": currency_value,
        "keywords": source.get("keywords"),
        "size_bytes": _coerce_int(size_value),
    }


def document_size_bytes(doc: Document) -> int:
    size_value = doc.size_bytes or doc.size or 0
    try:
        size = int(size_value or 0)
    except (TypeError, ValueError):
        size = 0
    if size > 0:
        return size
    storage_key = (doc.storage_key or doc.storage_path or "").strip()
    if storage_key.startswith("storage/"):
        storage_key = storage_key.removeprefix("storage/").lstrip("/")
    storage_path = resolve_document_path(doc.storage_path)
    if storage_path and os.path.exists(storage_path):
        try:
            return int(os.path.getsize(storage_path))
        except OSError:
            return 0
    if storage_key and (storage_key.startswith("companies/") or storage_key.startswith("documents/")):
        try:
            data = blob_storage().get_bytes(storage_key)
            return len(data)
        except Exception:
            return 0
    return 0


def backfill_document_fields(
    session: Session,
    documents: Iterable[Document],
    *,
    meta_map: dict[int, DocumentMeta] | None = None,
) -> None:
    doc_list = list(documents)
    if not doc_list:
        return
    if meta_map is None:
        doc_ids = [int(doc.id or 0) for doc in doc_list if doc.id]
        if doc_ids:
            metas = session.exec(
                select(DocumentMeta).where(DocumentMeta.document_id.in_(doc_ids))
            ).all()
            meta_map = {int(meta.document_id): meta for meta in metas if meta}
        else:
            meta_map = {}
    updated = False
    for doc in doc_list:
        doc_id = int(doc.id or 0)
        meta_values = resolve_document_meta_values(meta_map.get(doc_id))
        size_bytes = document_size_bytes(doc)
        meta_size = meta_values.get("size_bytes")
        if size_bytes <= 0 and isinstance(meta_size, int) and meta_size > 0:
            size_bytes = meta_size
        amount_total = doc.amount_total
        amount_net = doc.amount_net
        amount_tax = doc.amount_tax
        if amount_total is None:
            amount_total = meta_values.get("amount_total")
        if amount_net is None:
            amount_net = meta_values.get("amount_net")
        if amount_tax is None:
            amount_tax = meta_values.get("amount_tax")
        currency_value = (doc.currency or meta_values.get("currency") or "").strip()
        if size_bytes > 0 and (int(doc.size_bytes or 0) <= 0 or int(doc.size or 0) <= 0):
            doc.size_bytes = size_bytes
            doc.size = size_bytes
            updated = True
        if amount_total is not None and doc.amount_total is None:
            doc.amount_total = _coerce_float(amount_total)
            updated = True
        if amount_net is not None and doc.amount_net is None:
            doc.amount_net = _coerce_float(amount_net)
            updated = True
        if amount_tax is not None and doc.amount_tax is None:
            doc.amount_tax = _coerce_float(amount_tax)
            updated = True
        if currency_value and not (doc.currency or "").strip():
            doc.currency = currency_value
            updated = True
    if updated:
        session.commit()


def serialize_document(document: Document) -> dict:
    doc_source = document.source.value if isinstance(document.source, DocumentSource) else (document.source or "")
    doc_type = _extension(document.original_filename or "")
    return {
        "id": int(document.id or 0),
        "company_id": int(document.company_id),
        "original_filename": document.original_filename or "",
        "storage_key": document.storage_key or "",
        "mime": document.mime or "",
        "size": int(document.size or 0),
        "size_bytes": int(document.size_bytes or document.size or 0),
        "sha256": document.sha256 or "",
        "source": doc_source,
        "title": document.title or "",
        "type": doc_type,
        "vendor": document.vendor or "",
        "doc_number": document.doc_number or "",
        "doc_date": document.doc_date or "",
        "amount_total": document.amount_total,
        "amount_net": document.amount_net,
        "amount_tax": document.amount_tax,
        "currency": document.currency or "",
        "description": document.description or "",
        "keywords_json": document.keywords_json or "[]",
        "created_at": (
            document.created_at.isoformat()
            if hasattr(document.created_at, "isoformat")
            else (document.created_at or "")
        ),
    }


def document_matches_filters(
    document: Document,
    *,
    query: str,
    source: str,
    doc_type: str,
    date_from: str,
    date_to: str,
) -> bool:
    if query:
        haystack = f"{document.title} {document.original_filename}".lower()
        if query.lower() not in haystack:
            return False
    doc_source = document.source.value if isinstance(document.source, DocumentSource) else (document.source or "")
    if source and doc_source.lower() != source.lower():
        return False
    doc_ext = _extension(document.original_filename or "")
    if doc_type and doc_ext.lower() != doc_type.lower():
        return False
    filter_date = _document_filter_date(document)
    if date_from and filter_date < _parse_iso_date(date_from):
        return False
    if date_to and filter_date > _parse_iso_date(date_to):
        return False
    return True
