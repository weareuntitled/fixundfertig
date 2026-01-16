from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime
from pathlib import Path

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
