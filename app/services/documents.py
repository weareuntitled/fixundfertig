from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from data import Document
from services.storage import (
    company_document_dir,
    company_document_path,
    ensure_company_dirs,
)

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_DOCUMENT_SIZE_BYTES = 15 * 1024 * 1024


def _safe_filename(value: str) -> str:
    name = os.path.basename(value or "").strip() or "upload"
    return name.replace(" ", "_")


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


def build_document_record(
    company_id: int,
    filename: str,
    *,
    mime_type: str,
    size_bytes: int,
    source: str,
    doc_type: str,
    original_filename: str,
) -> Document:
    safe_name = _safe_filename(filename)
    return Document(
        company_id=company_id,
        filename=safe_name,
        original_filename=original_filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        source=source,
        doc_type=doc_type,
    )


def set_document_storage_path(document: Document) -> None:
    if not document.id:
        raise ValueError("Document must be persisted before setting storage path")
    ensure_company_dirs(document.company_id)
    document.storage_path = company_document_path(
        document.company_id,
        document.id,
        document.filename,
    )
    if hasattr(document, "storage_key"):
        document.storage_key = document.storage_path


def resolve_document_path(storage_path: str) -> str:
    if not storage_path:
        return ""
    if os.path.isabs(storage_path) or storage_path.startswith("storage/"):
        return storage_path
    return os.path.join("storage", storage_path)


def ensure_document_dir(company_id: int, document_id: int) -> str:
    directory = company_document_dir(company_id, document_id)
    os.makedirs(directory, exist_ok=True)
    return directory


def serialize_document(document: Document) -> dict:
    return {
        "id": int(document.id or 0),
        "company_id": int(document.company_id),
        "filename": document.filename or "",
        "original_filename": document.original_filename or "",
        "mime_type": document.mime_type or "",
        "size_bytes": int(document.size_bytes or 0),
        "source": document.source or "",
        "type": document.doc_type or "",
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
        haystack = f"{document.filename} {document.original_filename}".lower()
        if query.lower() not in haystack:
            return False
    if source and (document.source or "").lower() != source.lower():
        return False
    if doc_type and (document.doc_type or "").lower() != doc_type.lower():
        return False
    created_at = document.created_at
    if not isinstance(created_at, datetime):
        created_at = _parse_iso_date(str(created_at))
    if date_from and created_at < _parse_iso_date(date_from):
        return False
    if date_to and created_at > _parse_iso_date(date_to):
        return False
    return True
