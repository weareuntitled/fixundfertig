# =========================
# APP/API/DOCUMENTS.PY
# =========================
"""
Documents API: /api/documents[/...]

Endpoints (Stand 2026-06-10):
- GET    /api/documents                 — Liste (mit Filter q, source, type, date_from, date_to)
- GET    /api/documents/{id}/file       — File-Stream (PDF inline, andere als Download)
- DELETE /api/documents/{id}            — Löschen

Upload (`POST /api/documents/upload`) bleibt in `app/main.py` bis zur vollständigen
Refactor von NiceGUI-spezifischen Helpers (`_build_document_storage_path`, etc.).
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Iterator

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlmodel import select

from data import Company, Document, DocumentMeta
from dependencies import db_session, get_current_company, require_session_auth
from services.blob_storage import blob_storage
from services.documents import (
    backfill_document_fields,
    build_document_record,
    build_display_title,
    document_matches_filters,
    normalize_keywords,
    resolve_document_path,
    safe_filename,
    serialize_document,
    validate_document_upload,
)


router = APIRouter(prefix="/api/documents", tags=["documents"])

_MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
_ALLOWED_EXTS = {"pdf", "jpg", "jpeg", "png"}


@router.get("", response_model=list[dict])
def list_documents(
    q: str = "",
    source: str = "",
    type: str = "",
    date_from: str = "",
    date_to: str = "",
    _user_id: int = Depends(require_session_auth),
    company=Depends(get_current_company),
    session: Iterator = Depends(db_session),
):
    documents = session.exec(
        select(Document).where(Document.company_id == int(company.id))
    ).all()
    filtered = [
        doc
        for doc in documents
        if document_matches_filters(
            doc,
            query=(q or "").strip(),
            source=(source or "").strip(),
            doc_type=(type or "").strip(),
            date_from=(date_from or "").strip(),
            date_to=(date_to or "").strip(),
        )
    ]

    def _sort_key(doc: Document):
        created_at = doc.created_at
        if isinstance(created_at, datetime):
            return created_at
        try:
            return datetime.fromisoformat(str(created_at))
        except Exception:
            return datetime.min

    filtered.sort(key=_sort_key, reverse=True)
    backfill_document_fields(session, filtered)
    return [serialize_document(doc) for doc in filtered]


@router.get("/{document_id}/file")
def document_file(
    document_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    document = session.get(Document, int(document_id))
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    company = session.get(Company, int(document.company_id))
    if not company or company.user_id != _user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    storage_path = resolve_document_path(document.storage_path)
    storage_key = (document.storage_key or document.storage_path or "").strip()
    if storage_key.startswith("storage/"):
        storage_key = storage_key.removeprefix("storage/").lstrip("/")
    content_type = document.mime or "application/octet-stream"
    if content_type.endswith("/pdf") or content_type.startswith("image/"):
        disposition = "inline"
    else:
        disposition = "attachment"
    headers = {
        "Content-Disposition": f'{disposition}; filename="{document.original_filename or "document"}"'
    }

    if storage_path and storage_path.exists():
        return FileResponse(str(storage_path), media_type=content_type, headers=headers)

    if storage_key and (storage_key.startswith("companies/") or storage_key.startswith("documents/")):
        storage = blob_storage()
        try:
            if storage.exists(storage_key):
                data = storage.get_bytes(storage_key)
                return Response(content=data, media_type=content_type, headers=headers)
        except Exception:
            pass

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    document = session.get(Document, int(document_id))
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    company = session.get(Company, int(document.company_id))
    if not company or company.user_id != _user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # Backward-compat: respect legacy readonly_mode (NiceGUI read-only share links).
    try:
        from nicegui import app
        if bool(app.storage.user.get("readonly_mode")):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only preview mode")
    except RuntimeError:
        # No NiceGUI storage initialized (e.g. pure API call) — skip check
        pass

    storage_path = resolve_document_path(document.storage_path)
    storage_key = (document.storage_key or document.storage_path or "").strip()
    if storage_key.startswith("storage/"):
        storage_key = storage_key.removeprefix("storage/").lstrip("/")
    if storage_path and storage_path.exists():
        try:
            storage_path.unlink()
        except OSError:
            pass
    if storage_key and (storage_key.startswith("companies/") or storage_key.startswith("documents/")):
        try:
            blob_storage().delete(storage_key)
        except Exception:
            pass

    meta = session.exec(
        select(DocumentMeta).where(DocumentMeta.document_id == int(document_id))
    ).first()
    if meta:
        session.delete(meta)
    session.delete(document)
    session.commit()
    return {"status": "deleted"}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = None,
    description: str | None = None,
    vendor: str | None = None,
    doc_number: str | None = None,
    doc_date: str | None = None,
    amount_total: str | None = None,
    amount_net: str | None = None,
    amount_tax: str | None = None,
    currency: str | None = None,
    keywords: str | None = None,
    company=Depends(get_current_company),
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Upload a document (PDF / JPG / PNG, max 15 MB)."""
    filename_raw = file.filename or ""
    contents = await file.read()

    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Datei zu groß (>{_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )

    try:
        validate_document_upload(safe_filename(filename_raw), len(contents))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    ext = os.path.splitext(filename_raw)[1].lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dateityp nicht erlaubt: .{ext}",
        )

    mime_type = file.content_type or {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "png": "image/png",
    }.get(ext, "application/octet-stream")

    sha256 = hashlib.sha256(contents).hexdigest()
    size_bytes = len(contents)
    title_value = (title or "").strip() or build_display_title(
        (vendor or "").strip(),
        (doc_date or "").strip() or None,
        float(amount_total) if amount_total else None,
        (currency or "").strip() or None,
        filename_raw,
    )

    document = build_document_record(
        int(company.id),
        filename_raw,
        mime_type=mime_type,
        size_bytes=size_bytes,
        source="MANUAL",
        doc_type=ext,
        title=title_value,
        description=(description or "").strip(),
        vendor=(vendor or "").strip(),
        doc_number=(doc_number or "").strip(),
        doc_date=(doc_date or "").strip() or None,
        amount_total=float(amount_total) if amount_total else None,
        amount_net=float(amount_net) if amount_net else None,
        amount_tax=float(amount_tax) if amount_tax else None,
        currency=(currency or "").strip() or None,
    )
    document.keywords_json = normalize_keywords(keywords)
    document.mime = mime_type
    document.size = size_bytes
    document.sha256 = sha256
    session.add(document)
    session.flush()

    storage_path = f"companies/{int(company.id)}/documents/{int(document.id)}/{safe_filename(filename_raw)}"
    document.storage_key = storage_path
    document.storage_path = storage_path

    try:
        blob_storage().put_bytes(storage_path, contents, mime_type)
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to store file: {exc}") from exc

    session.commit()
    session.refresh(document)
    return serialize_document(document)
