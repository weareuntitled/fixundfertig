"""N8N webhook endpoints and models extracted from main.py."""
from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from threading import Lock

from fastapi import HTTPException, Request, UploadFile, File, Form, Header
from fastapi.responses import JSONResponse
from nicegui import app, helpers
from pydantic import BaseModel, ConfigDict, field_validator
from sqlmodel import select

from data import Company, Document, DocumentMeta, WebhookEvent, get_session
from services.blob_storage import blob_storage
from services.documents import (
    build_document_record,
    build_display_title,
    normalize_keywords,
    safe_filename,
    serialize_document,
    validate_document_upload,
)

logger = logging.getLogger(__name__)

_N8N_MIN_PAYLOAD_BYTES = 32
_N8N_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_N8N_MONEY_PATTERN = re.compile(r"^-?\d+\.\d{2}$")

_IS_PYTEST = helpers.is_pytest()
_FF_ENV = (os.getenv("FF_ENV") or "").strip().lower() or ("test" if _IS_PYTEST else "development")
_MAX_UPLOAD_BYTES = int((os.getenv("FF_MAX_UPLOAD_BYTES") or "").strip() or 10 * 1024 * 1024)
_RATELIMIT_WEBHOOKS_PER_MIN = int((os.getenv("FF_RATELIMIT_WEBHOOKS_PER_MIN") or "").strip() or 120)

_CACHE_TTL_SECONDS = 300
_CACHE_MAXSIZE = 256
_CACHE_KEY_TYPE = tuple[int, int]
_cachetools_spec = importlib.util.find_spec("cachetools")
if _cachetools_spec is not None:
    from cachetools import TTLCache
    _invoice_pdf_cache = TTLCache(maxsize=_CACHE_MAXSIZE, ttl=_CACHE_TTL_SECONDS)
else:
    _invoice_pdf_cache: dict[_CACHE_KEY_TYPE, tuple[float, bytes]] = {}


class N8NExtractedPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    vendor: str | None = None
    doc_date: str | None = None
    amount_total: str | None = None
    amount_net: str | None = None
    amount_tax: str | None = None
    currency: str | None = None
    doc_number: str | None = None
    title: str | None = None
    summary: str | None = None
    keywords: list[str] | str | None = None
    line_items: list[object] | None = None
    compliance_flags: list[object] | None = None
    sha256: str | None = None

    @field_validator(
        "vendor", "doc_date", "currency", "doc_number", "title", "summary", "sha256",
        mode="before",
    )
    @classmethod
    def _strip_optional_strings(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("keywords", mode="before")
    @classmethod
    def _strip_keywords(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("doc_date")
    @classmethod
    def _validate_doc_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("doc_date must be a string")
        if not _N8N_DATE_PATTERN.fullmatch(value):
            raise ValueError("doc_date must be YYYY-MM-DD")
        try:
            from datetime import datetime
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("doc_date must be YYYY-MM-DD") from exc
        return value

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("currency must be a string")
        normalized = value.strip().upper()
        if len(normalized) != 3:
            raise ValueError("currency must be 3 letters")
        return normalized

    @field_validator("amount_total", "amount_net", "amount_tax", mode="before")
    @classmethod
    def _validate_amounts(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if _N8N_MONEY_PATTERN.fullmatch(stripped):
                return stripped
            raise ValueError("amount must be a decimal with exactly 2 places")
        raise ValueError("amount must be a number or string")


N8N_INGEST_OPENAPI = {
    "requestBody": {
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["event_id", "company_id", "file_base64"],
                    "properties": {
                        "event_id": {"type": "string"},
                        "company_id": {"type": "integer"},
                        "file_base64": {"type": "string"},
                        "file_name": {"type": "string"},
                    },
                }
            }
        }
    }
}


class N8NIngestPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str
    company_id: int
    file_base64: str
    file_name: str | None = None
    extracted: N8NExtractedPayload | None = None


def _forbidden(detail: str = "Forbidden") -> None:
    raise HTTPException(status_code=403, detail=detail)


def _parse_n8n_file_payload(file_base64: object) -> tuple[bytes, str]:
    if not isinstance(file_base64, str) or not file_base64.strip():
        raise HTTPException(status_code=400, detail="file_base64 must be a non-empty string")
    raw = file_base64
    mime_from_prefix = ""
    if raw.startswith("data:"):
        try:
            header, encoded = raw.split(",", 1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid data URI")
        parts = header.split(";")
        if len(parts) >= 2 and parts[1].startswith("base64"):
            encoded = encoded
        mime_from_prefix = parts[0].removeprefix("data:").strip()
        raw = encoded
    file_bytes = base64.b64decode(raw)
    if len(file_bytes) < _N8N_MIN_PAYLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Payload too small")
    return file_bytes, mime_from_prefix


def _validate_n8n_file_signature(file_bytes: bytes, mime_type: str, ext: str) -> None:
    if ext == "pdf" and not file_bytes.lstrip()[:5] == b"%PDF-":
        raise HTTPException(status_code=400, detail="File does not look like a PDF")
    if mime_type.startswith("image/") and ext not in {"png", "jpg", "jpeg"}:
        raise HTTPException(status_code=400, detail="Unsupported image format")


def _parse_optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _payload_text(payload: dict, key: str) -> str:
    raw = payload.get(key)
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    return str(raw).strip()


def _build_legacy_extracted_payload(payload: dict) -> dict:
    extracted: dict = {}
    for key in (
        "vendor", "doc_date", "amount_total", "amount_net", "amount_tax",
        "currency", "doc_number", "title", "summary", "keywords",
        "line_items", "compliance_flags",
    ):
        if key in payload and payload[key] is not None:
            extracted[key] = payload[key]
    return extracted


def _resolve_extracted_payload(payload: dict) -> dict:
    nested = payload.get("extracted")
    if isinstance(nested, dict):
        return {k: v for k, v in nested.items() if v is not None}
    return _build_legacy_extracted_payload(payload)


def _validate_extracted_payload(extracted: dict) -> dict:
    validated = N8NExtractedPayload(**extracted)
    return validated.model_dump(exclude_none=True, exclude_unset=True)


def _build_document_storage_path(company_id: int, ext: str, event_id: str) -> str:
    from datetime import datetime
    date_part = datetime.utcnow().strftime("%Y%m%d")
    return f"companies/{company_id}/uploads/{date_part}/{event_id}.{ext}"


def _resolve_document_storage_path(storage_path: str | None) -> Path | None:
    if not storage_path:
        return None
    p = Path(storage_path)
    if p.is_absolute():
        return p if p.exists() else None
    storage_root = Path(os.getenv("STORAGE_LOCAL_ROOT", "storage") or "storage")
    return storage_root / p


def _json_text(value: object | None, *, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or default
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return default


_IS_PYTEST = helpers.is_pytest()
_MAX_UPLOAD_BYTES = int((os.getenv("FF_MAX_UPLOAD_BYTES") or "").strip() or 10 * 1024 * 1024)
_RATELIMIT_WEBHOOKS_PER_MIN = int((os.getenv("FF_RATELIMIT_WEBHOOKS_PER_MIN") or "").strip() or 120)

_RATE_LOCK = Lock()
_cachetools_rt = importlib.util.find_spec("cachetools")
if _cachetools_rt is not None:
    from cachetools import TTLCache as _TTLCache
    _RATE_COUNTERS: dict[str, int] = _TTLCache(maxsize=4096, ttl=60)  # type: ignore[name-defined]
else:
    _RATE_COUNTERS: dict[str, tuple[float, int]] = {}


def _client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",", 1)[0].strip()
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"


def _rate_limit(request: Request, *, bucket: str, limit_per_min: int, key_suffix: str = "") -> None:
    if limit_per_min <= 0:
        return
    client_ip = _client_ip(request)
    key = f"{bucket}:{client_ip}"
    if key_suffix:
        key = f"{key}:{key_suffix}"

    with _RATE_LOCK:
        if _cachetools_rt is not None:
            current = int(_RATE_COUNTERS.get(key, 0))  # type: ignore[attr-defined]
            if current >= limit_per_min:
                raise HTTPException(status_code=429, detail="Too many requests")
            _RATE_COUNTERS[key] = current + 1  # type: ignore[index]
            return

        now = time.monotonic()
        entry = _RATE_COUNTERS.get(key)
        if not entry or now >= entry[0]:
            expires_at, current = now + 60, 0
        else:
            expires_at, current = entry
        if current >= limit_per_min:
            raise HTTPException(status_code=429, detail="Too many requests")
        _RATE_COUNTERS[key] = (expires_at, current + 1)


@app.post("/api/webhooks/n8n/ingest")
async def n8n_ingest(request: Request):
    from pages._shared import get_current_user_id

    raw_body = await request.body()
    if len(raw_body) > _MAX_UPLOAD_BYTES * 2:
        raise HTTPException(status_code=413, detail="Payload too large")
    timestamp_header = (request.headers.get("X-Timestamp") or "").strip()
    secret_header = (request.headers.get("X-N8N-Secret") or request.headers.get("X-API-KEY") or "").strip()
    signature_header = (request.headers.get("X-Signature") or "").strip()
    event_id_header = (request.headers.get("X-Event-Id") or "").strip()

    if not timestamp_header:
        _forbidden()

    try:
        timestamp = int(timestamp_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp")

    drift = abs(int(time.time()) - timestamp)
    if drift > 300:
        _forbidden()

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload structure")

    extracted_payload = _resolve_extracted_payload(payload)
    extracted = _validate_extracted_payload(extracted_payload)

    event_id = event_id_header or str(payload.get("event_id") or "").strip()
    company_id_raw = payload.get("company_id")
    file_base64 = payload.get("file_base64")
    if not event_id or company_id_raw is None or file_base64 is None:
        raise HTTPException(status_code=400, detail="Missing required payload fields")

    try:
        company_id = int(company_id_raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid company_id")

    _rate_limit(request, bucket="webhooks", limit_per_min=_RATELIMIT_WEBHOOKS_PER_MIN, key_suffix=str(company_id))

    with get_session() as session:
        company = session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        if not bool(getattr(company, "n8n_enabled", False)):
            _forbidden()
        secret = (getattr(company, "n8n_secret", "") or "").strip()
        if not secret:
            _forbidden()
        if signature_header:
            signature_input = f"{timestamp}.".encode("utf-8") + raw_body
            expected_signature = hmac.new(secret.encode("utf-8"), signature_input, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_signature, signature_header):
                _forbidden()
        else:
            if not secret_header or not event_id_header:
                _forbidden()
            if not hmac.compare_digest(secret, secret_header):
                _forbidden()

        existing_event = session.exec(
            select(WebhookEvent).where(WebhookEvent.event_id == event_id)
        ).first()
        if existing_event:
            raise HTTPException(status_code=409, detail="Duplicate event")

        try:
            file_bytes, mime_from_prefix = _parse_n8n_file_payload(file_base64)
        except HTTPException as exc:
            logger.warning(
                "n8n ingest rejected payload event_id=%s company_id=%s reason=%s",
                event_id,
                company_id_raw,
                exc.detail,
            )
            raise

        file_name = (payload.get("file_name") or payload.get("filename") or "").strip()
        if not file_name:
            if mime_from_prefix == "application/pdf":
                file_name = f"document_{event_id}.pdf"
            elif mime_from_prefix == "image/png":
                file_name = f"document_{event_id}.png"
            elif mime_from_prefix == "image/jpeg":
                file_name = f"document_{event_id}.jpg"
            else:
                file_name = f"document_{event_id}.bin"
        original_filename = file_name
        safe_name = safe_filename(file_name)

        validate_document_upload(safe_name, len(file_bytes))

        ext = os.path.splitext(safe_name)[1].lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"
        mime_type = mime_from_prefix or {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "png": "image/png",
        }.get(ext, "application/octet-stream")
        _validate_n8n_file_signature(file_bytes, mime_type, ext)

        vendor_value = (extracted.get("vendor") or "").strip()
        doc_date_value = (extracted.get("doc_date") or "").strip() or None
        amount_value = _parse_optional_float(extracted.get("amount_total"))
        amount_net_value = _parse_optional_float(extracted.get("amount_net"))
        amount_tax_value = _parse_optional_float(extracted.get("amount_tax"))
        currency_value = (extracted.get("currency") or "").strip() or None
        doc_number_value = (extracted.get("doc_number") or "").strip()
        title_value = (extracted.get("title") or "").strip()
        if not title_value:
            title_value = build_display_title(
                vendor_value,
                doc_date_value,
                amount_value,
                currency_value,
                safe_name,
            )
        description_value = (extracted.get("summary") or "").strip()
        keywords_value = extracted.get("keywords")

        provided_sha256 = (extracted.get("sha256") or "").strip()
        if re.fullmatch(r"[A-Fa-f0-9]{64}", provided_sha256):
            sha256 = provided_sha256.lower()
        else:
            sha256 = hashlib.sha256(file_bytes).hexdigest()
        size_bytes = len(file_bytes)
        document = build_document_record(
            company_id,
            original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            source="n8n",
            doc_type=ext,
            storage_key="pending",
            storage_path="",
            title=title_value,
            description=description_value,
            vendor=vendor_value,
            doc_number=doc_number_value,
            doc_date=doc_date_value,
            amount_total=amount_value,
            amount_net=amount_net_value,
            amount_tax=amount_tax_value,
            currency=currency_value,
        )
        document.keywords_json = normalize_keywords(keywords_value)
        session.add(document)
        session.flush()

        storage_path = f"companies/{company_id}/uploads/{datetime.utcnow().strftime('%Y%m%d')}/{event_id}.{ext}"
        document.storage_path = storage_path
        document.storage_key = storage_path

        resolved = _resolve_document_storage_path(storage_path)
        if resolved is None:
            session.rollback()
            raise HTTPException(status_code=500, detail="Invalid storage path")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        try:
            resolved.write_bytes(file_bytes)
        except OSError as exc:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to store file: {exc}") from exc
        session.commit()
        session.refresh(document)

        raw_payload_json = json.dumps(payload, ensure_ascii=False)
        line_items_json = _json_text(
            extracted.get("line_items") if isinstance(extracted, dict) else None,
            default="[]",
        )
        compliance_flags_json = _json_text(
            extracted.get("compliance_flags") if isinstance(extracted, dict) else None,
            default="[]",
        )
        meta = session.exec(
            select(DocumentMeta).where(DocumentMeta.document_id == int(document.id or 0))
        ).first()
        if meta:
            meta.raw_payload_json = raw_payload_json
            meta.line_items_json = line_items_json
            meta.compliance_flags_json = compliance_flags_json
        else:
            session.add(
                DocumentMeta(
                    document_id=int(document.id or 0),
                    raw_payload_json=raw_payload_json,
                    line_items_json=line_items_json,
                    compliance_flags_json=compliance_flags_json,
                )
            )

        session.add(WebhookEvent(event_id=event_id, source="n8n"))
        session.commit()
        session.refresh(document)
        return {"status": "ok", "document_id": int(document.id or 0)}


@app.post("/api/webhooks/n8n/upload")
async def n8n_upload(
    request: Request,
    file: UploadFile = File(...),
    payload_json: str = Form(...),
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    x_n8n_secret: str | None = Header(None, alias="X-N8N-Secret"),
    file_name: str | None = Form(None),
    title: str | None = Form(None),
    description: str | None = Form(None),
    vendor: str | None = Form(None),
    doc_number: str | None = Form(None),
    doc_date: str | None = Form(None),
    amount_total: str | None = Form(None),
    amount_net: str | None = Form(None),
    amount_tax: str | None = Form(None),
    currency: str | None = Form(None),
    keywords: str | None = Form(None),
) -> Response:
    if not x_company_id or not x_n8n_secret:
        _forbidden()
    try:
        company_id = int(x_company_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid company id")

    _rate_limit(request, bucket="webhooks", limit_per_min=_RATELIMIT_WEBHOOKS_PER_MIN, key_suffix=str(company_id))

    try:
        payload = json.loads(payload_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload_json")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload_json")

    extracted_payload = _resolve_extracted_payload(payload)
    extracted = _validate_extracted_payload(extracted_payload)

    raw_filename = (
        file_name
        or payload.get("file_name")
        or payload.get("filename")
        or payload.get("name")
        or file.filename
        or "document"
    )
    safe_name = safe_filename(str(raw_filename))

    file_bytes = await file.read()
    validate_document_upload(safe_name, len(file_bytes))
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    mime = (file.content_type or "").strip()
    if not mime:
        ext = os.path.splitext(safe_name)[1].lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"
        mime = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "png": "image/png",
        }.get(ext, "application/octet-stream")
    ext_for_sig = os.path.splitext(safe_name)[1].lower().lstrip(".")
    if ext_for_sig == "jpeg":
        ext_for_sig = "jpg"
    _validate_n8n_file_signature(file_bytes, mime, ext_for_sig)

    vendor_value = (vendor or extracted.get("vendor") or payload.get("vendor") or "").strip()
    doc_number_value = (doc_number or extracted.get("doc_number") or payload.get("doc_number") or "").strip()
    doc_date_value = (doc_date or extracted.get("doc_date") or payload.get("doc_date") or "").strip() or None
    amount_value = _parse_optional_float(
        amount_total if amount_total is not None else extracted.get("amount_total") or payload.get("amount_total")
    )
    amount_net_value = _parse_optional_float(
        amount_net if amount_net is not None else extracted.get("amount_net") or payload.get("amount_net")
    )
    amount_tax_value = _parse_optional_float(
        amount_tax if amount_tax is not None else extracted.get("amount_tax") or payload.get("amount_tax")
    )
    currency_value = (currency or extracted.get("currency") or payload.get("currency") or "").strip() or None
    keywords_value = keywords or extracted.get("keywords") or payload.get("keywords")
    title_value = (title or extracted.get("title") or payload.get("title") or "").strip()
    if not title_value:
        title_value = build_display_title(
            vendor_value,
            doc_date_value,
            amount_value,
            currency_value,
            safe_name,
        )
    description_value = (description or extracted.get("summary") or _payload_text(payload, "summary")).strip()

    with get_session() as session:
        company = session.get(Company, company_id)
        if not company:
            _forbidden()
        if not bool(getattr(company, "n8n_enabled", False)):
            _forbidden()
        secret = (getattr(company, "n8n_secret", "") or "").strip()
        if not secret or not hmac.compare_digest(secret, x_n8n_secret):
            _forbidden()

        existing = session.exec(
            select(Document).where(
                Document.company_id == company_id,
                Document.sha256 == sha256,
                Document.source.in_(["n8n", "N8N"]),
            )
        ).first()
        if existing:
            return JSONResponse(
                status_code=200,
                content={
                    "ok": True,
                    "duplicate": True,
                    "document_id": int(existing.id or 0),
                },
            )

        ext = os.path.splitext(safe_name)[1].lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"
        document = build_document_record(
            company_id,
            str(raw_filename),
            mime_type=mime,
            size_bytes=len(file_bytes),
            sha256=sha256,
            source="n8n",
            doc_type=ext,
            storage_key="pending",
            storage_path="",
            title=title_value,
            description=description_value,
            vendor=vendor_value,
            doc_number=doc_number_value,
            doc_date=doc_date_value,
            amount_total=amount_value,
            amount_net=amount_net_value,
            amount_tax=amount_tax_value,
            currency=currency_value,
        )
        document.filename = safe_name
        document.keywords_json = normalize_keywords(keywords_value)
        document.invoice_date = doc_date_value
        document.gross_amount = amount_value
        document.net_amount = amount_net_value
        document.tax_amount = amount_tax_value
        document.tax_treatment = str(extracted.get("tax_treatment") or payload.get("tax_treatment") or "").strip()
        document.document_type = str(extracted.get("document_type") or payload.get("document_type") or "").strip()
        session.add(document)
        session.flush()

        storage_path = f"companies/{company_id}/uploads/{datetime.utcnow().strftime('%Y%m%d')}/{safe_name}"
        document.storage_key = storage_path
        document.storage_path = storage_path

        resolved = _resolve_document_storage_path(storage_path)
        if resolved is None:
            session.rollback()
            raise HTTPException(status_code=500, detail="Invalid storage path")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        try:
            resolved.write_bytes(file_bytes)
        except OSError as exc:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to store file: {exc}") from exc

        raw_payload_json = json.dumps(payload, ensure_ascii=False)
        line_items_json = _json_text(extracted.get("line_items") if isinstance(extracted, dict) else None, default="[]")
        compliance_flags_json = _json_text(
            extracted.get("compliance_flags") if isinstance(extracted, dict) else None,
            default="[]",
        )
        meta = session.exec(
            select(DocumentMeta).where(DocumentMeta.document_id == int(document.id or 0))
        ).first()
        if meta:
            meta.raw_payload_json = raw_payload_json
            meta.line_items_json = line_items_json
            meta.compliance_flags_json = compliance_flags_json
        else:
            session.add(
                DocumentMeta(
                    document_id=int(document.id or 0),
                    raw_payload_json=raw_payload_json,
                    line_items_json=line_items_json,
                    compliance_flags_json=compliance_flags_json,
                )
            )

        session.commit()

        return JSONResponse(
            status_code=201,
            content={
                "ok": True,
                "duplicate": False,
                "document_id": int(document.id or 0),
            },
        )
