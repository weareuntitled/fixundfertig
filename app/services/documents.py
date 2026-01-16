from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException

from data import Document
from models.document import DocumentSource, safe_filename
from services.storage import company_documents_dir, ensure_company_dirs

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_DOCUMENT_SIZE_BYTES = 15 * 1024 * 1024


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
    name = (value or "").strip()
    if not name:
        return "document"
    name = os.path.basename(name)
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = name.strip("._-")
    return name or "document"


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
    mime: str,
    size: int,
    sha256: str,
    source: DocumentSource,
    storage_key: str | None = None,
    title: str = "",
    description: str = "",
    vendor: str = "",
    doc_date: str | None = None,
    amount_total: float | None = None,
    currency: str | None = None,
) -> Document:
    storage_key = storage_key or _storage_key_from_filename(original_filename)
    return Document(
        company_id=company_id,
        storage_key=storage_key,
        original_filename=original_filename,
        mime=mime,
        size=size,
        sha256=sha256,
        source=source,
        title=title,
        description=description,
        vendor=vendor,
        doc_date=doc_date,
        amount_total=amount_total,
        currency=currency,
    )
    if hasattr(document, "storage_key"):
        document.storage_key = document.storage_path


def document_storage_path(company_id: int, storage_key: str) -> str:
    if not storage_key:
        return ""
    ensure_company_dirs(company_id)
    if os.path.isabs(storage_key) or storage_key.startswith("storage/"):
        return storage_key
    return os.path.join(company_documents_dir(company_id), storage_key)


def ensure_document_dir(company_id: int) -> str:
    directory = company_documents_dir(company_id)
    os.makedirs(directory, exist_ok=True)
    return directory


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
        "sha256": document.sha256 or "",
        "source": doc_source,
        "title": document.title or "",
        "type": doc_type,
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
    created_at = document.created_at
    if not isinstance(created_at, datetime):
        created_at = _parse_iso_date(str(created_at))
    if date_from and created_at < _parse_iso_date(date_from):
        return False
    if date_to and created_at > _parse_iso_date(date_to):
        return False
    return True
