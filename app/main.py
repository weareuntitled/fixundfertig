# =========================
# APP/MAIN.PY (REPLACE FULL FILE)
# =========================

import base64
import hashlib
import hmac
import importlib.util
import json
import logging
import re
import mimetypes
import os
import time
from threading import Lock
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request as UrlRequest, urlopen

from fastapi import HTTPException, Response, UploadFile, File, Form, Header, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from nicegui import ui, app, helpers
from nicegui.storage import Storage, PseudoPersistentDict, request_contextvar
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from sqlmodel import select
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from env import load_env

# Load ".env" before importing modules that read env vars at import time.
load_env()

from logging_setup import setup_logging

setup_logging()

from auth_guard import clear_auth_session, is_authenticated, require_auth
from data import Company, Customer, Document, DocumentMeta, Invoice, User, WebhookEvent, get_session
from renderer import render_invoice_to_pdf_bytes
from styles import STYLE_BG, STYLE_BTN_ACCENT, STYLE_CONTAINER, STYLE_INPUT, STYLE_TAP_TARGET, STYLE_TEXT_MUTED
from ui_theme import apply_global_ui_theme
from invoice_numbering import build_invoice_filename
from pages import (
    render_dashboard,
    render_customers,
    render_customer_new,
    render_customer_detail,
    render_invoices,
    render_invoice_create,
    render_invoice_detail,
    render_expenses,
    render_documents,
    render_settings,
    render_invites,
    render_ledger,
    render_exports,
)
from pages._shared import get_current_user_id, get_primary_company, list_companies, _open_invoice_editor
from services.blob_storage import blob_storage, build_document_key
from services.storage import company_logo_path
from services.auth import ensure_owner_user, get_owner_email
from services.documents import (
    backfill_document_fields,
    build_document_record,
    build_display_title,
    document_matches_filters,
    document_storage_path,
    resolve_document_path,
    normalize_keywords,
    safe_filename,
    serialize_document,
    validate_document_upload,
)
_CACHE_TTL_SECONDS = 300
_CACHE_MAXSIZE = 256
_CACHE_KEY_TYPE = tuple[int, int]
_cachetools_spec = importlib.util.find_spec("cachetools")
if _cachetools_spec is not None:
    from cachetools import TTLCache
    _invoice_pdf_cache = TTLCache(maxsize=_CACHE_MAXSIZE, ttl=_CACHE_TTL_SECONDS)
else:
    _invoice_pdf_cache: dict[_CACHE_KEY_TYPE, tuple[float, bytes]] = {}

_DOCUMENT_STORAGE_ROOT = Path(os.getenv("STORAGE_LOCAL_ROOT", "storage") or "storage")
logger = logging.getLogger(__name__)
_N8N_MIN_PAYLOAD_BYTES = 32
_N8N_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_N8N_MONEY_PATTERN = re.compile(r"^-?\d+\.\d{2}$")

_IS_PYTEST = helpers.is_pytest()
_FF_ENV = (os.getenv("FF_ENV") or "").strip().lower() or ("test" if _IS_PYTEST else "development")
_APP_BASE_URL = (os.getenv("APP_BASE_URL") or "").strip()
_BASE_URL_IS_HTTPS = _APP_BASE_URL.lower().startswith("https://")
_IS_PROD = _FF_ENV in {"prod", "production"} or (_BASE_URL_IS_HTTPS and not _IS_PYTEST)


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_csv(name: str) -> list[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _require_storage_secret() -> str:
    secret = (os.getenv("STORAGE_SECRET") or "").strip()
    if _IS_PYTEST and len(secret) < 32:
        return "pytest-secret"
    if secret:
        if len(secret) < 32:
            raise RuntimeError("STORAGE_SECRET is too short; use a high-entropy value (>=32 chars).")
        return secret
    if _IS_PYTEST:
        return "pytest-secret"
    raise RuntimeError('Missing STORAGE_SECRET. Copy ".env.example" to ".env" and set a strong random value.')


_MAX_UPLOAD_BYTES = _env_int("FF_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
_RATELIMIT_LOGIN_PER_MIN = _env_int("FF_RATELIMIT_LOGIN_PER_MIN", 10)
_RATELIMIT_UPLOAD_PER_MIN = _env_int("FF_RATELIMIT_UPLOAD_PER_MIN", 30)
_RATELIMIT_WEBHOOKS_PER_MIN = _env_int("FF_RATELIMIT_WEBHOOKS_PER_MIN", 120)
_TRUST_PROXY_HEADERS = (os.getenv("FF_TRUST_PROXY_HEADERS") or ("1" if _IS_PROD else "0")).strip() == "1"

storage_secret = _require_storage_secret()
Storage.secret = storage_secret


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _derive_trusted_hosts() -> list[str]:
    explicit = _env_csv("FF_TRUSTED_HOSTS")
    if explicit:
        return explicit

    hosts: list[str] = []
    domain = (os.getenv("APP_DOMAIN") or "").strip()
    if domain:
        hosts.extend([domain, f"www.{domain}"])

    base_url = (os.getenv("APP_BASE_URL") or "").strip()
    if base_url:
        parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
        if parsed.hostname:
            hosts.append(parsed.hostname)

    if _IS_PYTEST:
        hosts.append("testserver")
    if not _IS_PROD:
        hosts.extend(["localhost", "127.0.0.1", "0.0.0.0"])

    return _dedupe_keep_order(hosts)


def _derive_cors_origins() -> list[str]:
    explicit = _env_csv("FF_CORS_ORIGINS")
    if explicit:
        return explicit

    origins: list[str] = []
    base_url = (os.getenv("APP_BASE_URL") or "").strip().rstrip("/")
    if base_url:
        if base_url.startswith(("http://", "https://")):
            origins.append(base_url)
        else:
            origins.append(f"https://{base_url}".rstrip("/"))

    domain = (os.getenv("APP_DOMAIN") or "").strip()
    if domain:
        origins.extend([f"https://{domain}", f"https://www.{domain}"])

    if _IS_PYTEST:
        origins.append("http://testserver")
    if not _IS_PROD:
        origins.extend(["http://localhost:8000", "http://127.0.0.1:8000"])

    return _dedupe_keep_order([origin.rstrip("/") for origin in origins])


def _configure_security_middleware() -> None:
    trusted_hosts = _derive_trusted_hosts()
    if _IS_PROD and not trusted_hosts:
        raise RuntimeError("Trusted hosts not configured. Set APP_DOMAIN or FF_TRUSTED_HOSTS.")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts or ["*"])

    cookie_secure_default = "1" if _IS_PROD else "0"
    cookie_secure = (os.getenv("FF_COOKIE_SECURE") or cookie_secure_default).strip() == "1"
    cookie_samesite = (os.getenv("FF_COOKIE_SAMESITE") or "strict").strip().lower()
    if cookie_samesite not in {"lax", "strict", "none"}:
        cookie_samesite = "strict"
    if cookie_samesite == "none" and not cookie_secure:
        raise RuntimeError("FF_COOKIE_SAMESITE=none requires FF_COOKIE_SECURE=1")

    session_cookie = (os.getenv("FF_SESSION_COOKIE") or "ff_session").strip() or "ff_session"
    session_max_age = _env_int("FF_SESSION_MAX_AGE_SECONDS", 60 * 60 * 24 * 14)
    app.add_middleware(
        SessionMiddleware,
        secret_key=storage_secret,
        session_cookie=session_cookie,
        same_site=cookie_samesite,
        https_only=cookie_secure,
        max_age=session_max_age,
    )

    cors_origins = _derive_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )


_configure_security_middleware()


def _forbidden(detail: str = "Forbidden") -> None:
    raise HTTPException(status_code=403, detail=detail)


def _client_ip(request: Request) -> str:
    if _TRUST_PROXY_HEADERS:
        xff = (request.headers.get("x-forwarded-for") or "").strip()
        if xff:
            return xff.split(",", 1)[0].strip()
        real_ip = (request.headers.get("x-real-ip") or "").strip()
        if real_ip:
            return real_ip
    if request.client:
        return request.client.host
    return "unknown"


_RATE_LOCK = Lock()
if _cachetools_spec is not None:
    _RATE_COUNTERS = TTLCache(maxsize=4096, ttl=60)  # type: ignore[name-defined]
else:
    _RATE_COUNTERS: dict[str, tuple[float, int]] = {}


def _rate_limit(request: Request, *, bucket: str, limit_per_min: int, key_suffix: str = "") -> None:
    if limit_per_min <= 0:
        return
    client_ip = _client_ip(request)
    key = f"{bucket}:{client_ip}"
    if key_suffix:
        key = f"{key}:{key_suffix}"

    with _RATE_LOCK:
        if _cachetools_spec is not None:
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
        "vendor",
        "doc_date",
        "currency",
        "doc_number",
        "title",
        "summary",
        "sha256",
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
            value = f"{value:.2f}"
        if not isinstance(value, str):
            raise ValueError("amount must be a string")
        stripped = value.strip()
        if not _N8N_MONEY_PATTERN.fullmatch(stripped):
            raise ValueError("amount must have 2 decimals")
        return stripped


class N8NIngestPayload(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"required": ["company_id", "file_base64"]},
    )

    company_id: int | None = None
    file_base64: str | None = None
    event_id: str | None = None
    file_name: str | None = None
    extracted: N8NExtractedPayload | None = None


def _get_cached_pdf(cache_key: _CACHE_KEY_TYPE) -> bytes | None:
    if _cachetools_spec is not None:
        return _invoice_pdf_cache.get(cache_key)
    entry = _invoice_pdf_cache.get(cache_key)
    if not entry:
        return None
    expires_at, payload = entry
    if time.monotonic() >= expires_at:
        _invoice_pdf_cache.pop(cache_key, None)
        return None
    return payload


def _store_cached_pdf(cache_key: _CACHE_KEY_TYPE, payload: bytes) -> None:
    if _cachetools_spec is not None:
        _invoice_pdf_cache[cache_key] = payload
        return
    _invoice_pdf_cache[cache_key] = (time.monotonic() + _CACHE_TTL_SECONDS, payload)


def _build_document_storage_path(
    company_id: int,
    document_id: int,
    filename: str,
    created_at: datetime | None,
) -> str:
    timestamp = created_at if isinstance(created_at, datetime) else datetime.utcnow()
    return build_document_key(company_id, document_id, filename, now=timestamp)


def _resolve_document_storage_path(storage_path: str | None) -> Path | None:
    resolved_path = resolve_document_path(storage_path)
    if not resolved_path:
        return None
    candidate = Path(resolved_path)
    if not candidate.is_absolute():
        root_name = _DOCUMENT_STORAGE_ROOT.name
        if not (candidate.parts and candidate.parts[0] == root_name):
            candidate = _DOCUMENT_STORAGE_ROOT / candidate
    resolved = candidate.resolve()
    root = _DOCUMENT_STORAGE_ROOT.resolve()
    if not str(resolved).startswith(f"{root}{os.sep}"):
        return None
    return resolved


def _parse_n8n_file_payload(file_base64: object) -> tuple[bytes, str]:
    raw_value = str(file_base64 or "").strip()
    if not raw_value:
        raise HTTPException(status_code=400, detail="Missing file_base64 payload")
    if "filesystem-v2" in raw_value:
        raise HTTPException(status_code=400, detail="Invalid file_base64 payload")

    mime_from_prefix = ""
    payload = raw_value
    if raw_value.startswith("data:"):
        if "," not in raw_value:
            raise HTTPException(status_code=400, detail="Invalid file_base64 prefix")
        header, payload = raw_value.split(",", 1)
        if ";base64" not in header:
            raise HTTPException(status_code=400, detail="Invalid file_base64 prefix")
        mime_from_prefix = header[5:header.index(";base64")].strip()
    elif "," in raw_value and "base64" in raw_value.split(",", 1)[0]:
        raise HTTPException(status_code=400, detail="Invalid file_base64 prefix")

    if "filesystem-v2" in payload:
        raise HTTPException(status_code=400, detail="Invalid file_base64 payload")

    try:
        file_bytes = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid file_base64 payload") from exc
    return file_bytes, mime_from_prefix


def _validate_n8n_file_signature(file_bytes: bytes, mime_type: str, ext: str) -> None:
    expected = ""
    if mime_type.startswith("image/"):
        expected = mime_type
    elif ext in {"pdf", "png", "jpg", "jpeg"}:
        expected = {
            "pdf": "application/pdf",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
        }[ext]

    if not expected:
        return
    if len(file_bytes) < _N8N_MIN_PAYLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Decoded file is too small")

    if expected == "application/pdf" and not file_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File content is not a valid PDF")
    if expected == "image/png" and not file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="File content is not a valid PNG")
    if expected == "image/jpeg" and not file_bytes.startswith(b"\xff\xd8"):
        raise HTTPException(status_code=400, detail="File content is not a valid JPEG")

app.add_static_files("/static", str(Path(__file__).resolve().parent / "static"))
if not _IS_PYTEST:
    try:
        ensure_owner_user()
    except Exception:
        logger.exception("Failed to ensure owner user")


def _require_api_auth() -> None:
    if not is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")


def _resolve_active_company(session, user_id: int) -> Company:
    companies = list_companies(session, user_id)
    active_id = app.storage.user.get("active_company_id")
    try:
        active_id = int(active_id) if active_id is not None else None
    except Exception:
        active_id = None
    if active_id:
        company = next((c for c in companies if int(c.id or 0) == active_id), None)
        if company:
            return company
    company = companies[0] if companies else get_primary_company(session, user_id)
    if company and company.id:
        app.storage.user["active_company_id"] = int(company.id)
    return company


def _resolve_invoice_pdf_path(filename: str | None) -> Path | None:
    if not filename:
        return None
    if Path(filename).is_absolute() or str(filename).startswith("storage/"):
        return Path(filename)
    return Path("storage/invoices") / filename


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


def _format_nominatim_result(item: dict) -> dict:
    address = item.get("address") or {}
    road = address.get("road") or address.get("pedestrian") or address.get("path") or ""
    house_number = address.get("house_number") or ""
    street = " ".join(part for part in [road, house_number] if part).strip()
    if not street:
        street = address.get("street") or ""
    postal_code = address.get("postcode") or ""
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
        or ""
    )
    country_code = (address.get("country_code") or "").upper()
    country = address.get("country") or country_code
    label = item.get("display_name") or ", ".join(
        part for part in [street, f"{postal_code} {city}".strip(), country] if part
    )
    return {
        "label": label,
        "street": street,
        "zip": postal_code,
        "city": city,
        "country": country,
    }


@app.get("/api/address-autocomplete")
def address_autocomplete(q: str = "", country: str = "DE"):
    query = (q or "").strip()
    if len(query) < 3:
        return []

    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": 6,
    }
    if country:
        params["countrycodes"] = country.lower()
    url = f"https://nominatim.openstreetmap.org/search?{urlencode(params)}"
    request = UrlRequest(
        url,
        headers={
            "User-Agent": "FixundFertig/1.0 (autocomplete)",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    if not isinstance(payload, list):
        return []
    return [_format_nominatim_result(item) for item in payload]


N8N_INGEST_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {"application/json": {"schema": N8NIngestPayload.model_json_schema()}},
    }
}


@app.post("/api/webhooks/n8n/ingest", openapi_extra=N8N_INGEST_OPENAPI)
async def n8n_ingest(request: Request):
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

        storage_path = _build_document_storage_path(
            company_id,
            int(document.id or 0),
            safe_name,
            document.created_at,
        )
        document.storage_path = storage_path
        document.storage_key = storage_path

        resolved_path = _resolve_document_storage_path(storage_path)
        if resolved_path is None:
            session.rollback()
            raise HTTPException(status_code=500, detail="Invalid storage path")
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            resolved_path.write_bytes(file_bytes)
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


def _parse_optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _payload_text(payload: dict, key: str) -> str:
    value = payload.get(key)
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _build_legacy_extracted_payload(payload: dict) -> dict:
    legacy_keys = (
        "vendor",
        "doc_date",
        "amount_total",
        "amount_net",
        "amount_tax",
        "currency",
        "doc_number",
        "title",
        "summary",
        "keywords",
        "line_items",
        "compliance_flags",
        "sha256",
    )
    extracted: dict = {}
    for key in legacy_keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        if value is None:
            continue
        extracted[key] = value
    return extracted


def _resolve_extracted_payload(payload: dict) -> dict:
    if "extracted" in payload:
        extracted_raw = payload.get("extracted")
        if extracted_raw is None:
            return _build_legacy_extracted_payload(payload)
        if not isinstance(extracted_raw, dict):
            raise HTTPException(status_code=400, detail="Invalid extracted payload")
        return extracted_raw
    return _build_legacy_extracted_payload(payload)


def _validate_extracted_payload(extracted: dict) -> dict:
    if not extracted:
        return {}
    try:
        validated = N8NExtractedPayload.model_validate(extracted)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="Invalid extracted payload") from exc
    return validated.model_dump(exclude_none=True)


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
    vendor_details = payload.get("vendor_details")
    if not isinstance(vendor_details, dict):
        vendor_details = {}

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
        # Make sure stored filename matches our computed safe name (incl. .bnh adjustments).
        document.filename = safe_name
        document.keywords_json = normalize_keywords(keywords_value)
        # Backfill commonly used derived fields for downstream UI logic.
        document.invoice_date = doc_date_value
        document.gross_amount = amount_value
        document.net_amount = amount_net_value
        document.tax_amount = amount_tax_value
        document.tax_treatment = str(extracted.get("tax_treatment") or payload.get("tax_treatment") or "").strip()
        document.document_type = str(extracted.get("document_type") or payload.get("document_type") or "").strip()
        session.add(document)
        session.flush()

        storage_path = _build_document_storage_path(
            company_id,
            int(document.id or 0),
            safe_name,
            document.created_at,
        )
        document.storage_key = storage_path
        document.storage_path = storage_path

        resolved_path = _resolve_document_storage_path(storage_path)
        if resolved_path is None:
            session.rollback()
            raise HTTPException(status_code=500, detail="Invalid storage path")
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            resolved_path.write_bytes(file_bytes)
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


@app.post("/api/documents/upload")
async def document_upload(
    request: Request,
    company_id: int = Form(...),
    file: UploadFile = File(...),
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
) -> dict:
    _require_api_auth()
    _rate_limit(request, bucket="upload", limit_per_min=_RATELIMIT_UPLOAD_PER_MIN, key_suffix=str(company_id))
    filename = file.filename or ""
    contents = await file.read()
    validate_document_upload(filename, len(contents))

    with get_session() as session:
        user_id = get_current_user_id(session)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Unauthorized")

        company = session.get(Company, int(company_id))
        if not company or company.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"
        mime_type = file.content_type or {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "png": "image/png",
        }.get(ext, "")

        sha256 = hashlib.sha256(contents).hexdigest()
        size_bytes = len(contents)

        vendor_value = (vendor or "").strip()
        doc_number_value = (doc_number or "").strip()
        doc_date_value = (doc_date or "").strip() or None
        amount_value = _parse_optional_float(amount_total)
        amount_net_value = _parse_optional_float(amount_net)
        amount_tax_value = _parse_optional_float(amount_tax)
        currency_value = (currency or "").strip() or None
        title_value = (title or "").strip()
        if not title_value:
            title_value = build_display_title(
                vendor_value,
                doc_date_value,
                amount_value,
                currency_value,
                filename,
            )
        description_value = (description or "").strip()
        keywords_value = keywords

        try:
            document = build_document_record(
                int(company.id),
                filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                source="MANUAL",
                doc_type=ext,
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
            document.mime = mime_type
            document.size = size_bytes
            document.sha256 = sha256
            session.add(document)
            session.flush()

            storage_path = _build_document_storage_path(
                int(company.id),
                int(document.id),
                filename,
                document.created_at,
            )
            document.storage_key = storage_path
            document.storage_path = storage_path

            storage = blob_storage()
            try:
                storage.put_bytes(storage_path, contents, mime_type)
            except Exception as exc:
                session.rollback()
                raise HTTPException(status_code=500, detail=f"Failed to store file: {exc}") from exc
            session.commit()
            session.refresh(document)
        except HTTPException:
            raise
        except Exception:
            session.rollback()
            raise HTTPException(status_code=500, detail="Upload failed")

        return serialize_document(document)


@app.get("/api/documents")
def list_documents(
    q: str = "",
    source: str = "",
    type: str = "",
    date_from: str = "",
    date_to: str = "",
) -> list[dict]:
    _require_api_auth()
    with get_session() as session:
        user_id = get_current_user_id(session)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        company = _resolve_active_company(session, user_id)
        if not company or not company.id:
            return []

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


@app.get("/api/documents/{document_id}/file")
def document_file(document_id: int) -> Response:
    _require_api_auth()
    with get_session() as session:
        user_id = get_current_user_id(session)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Unauthorized")

        document = session.get(Document, int(document_id))
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        company = session.get(Company, int(document.company_id))
        if not company or company.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        storage_path = _resolve_document_storage_path(document.storage_path)
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

        blob_exists = None
        blob_size = None
        if storage_key and (storage_key.startswith("companies/") or storage_key.startswith("documents/")):
            storage = blob_storage()
            try:
                blob_exists = storage.exists(storage_key)
                if blob_exists:
                    data = storage.get_bytes(storage_key)
                    blob_size = len(data)
                    return Response(content=data, media_type=content_type, headers=headers)
            except Exception:
                logger.exception(
                    "Blob storage lookup failed for document_id=%s storage_key=%s",
                    document_id,
                    storage_key,
                )

        resolved_path = str(storage_path) if storage_path else ""
        local_exists = os.path.exists(resolved_path) if resolved_path else False
        local_size = None
        if local_exists:
            try:
                local_size = os.path.getsize(resolved_path)
            except OSError:
                local_size = None
        storage_local_root = os.getenv("STORAGE_LOCAL_ROOT", "storage") or "storage"

        logger.warning(
            (
                "Document file missing for document_id=%s expected_storage_path=%s "
                "resolved_storage_path=%s storage_key=%s storage_local_root=%s "
                "local_exists=%s local_size=%s blob_exists=%s blob_size=%s"
            ),
            document_id,
            document.storage_path,
            str(storage_path) if storage_path else None,
            storage_key,
            storage_local_root,
            local_exists,
            local_size,
            blob_exists,
            blob_size,
        )
        raise HTTPException(status_code=404, detail="File not found")


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: int) -> dict:
    _require_api_auth()
    with get_session() as session:
        user_id = get_current_user_id(session)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Unauthorized")

        document = session.get(Document, int(document_id))
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        company = session.get(Company, int(document.company_id))
        if not company or company.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        storage_path = _resolve_document_storage_path(document.storage_path)
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


@app.get("/viewer/invoice/{invoice_id}", response_class=HTMLResponse)
def invoice_viewer(invoice_id: int, rev: str | None = None) -> HTMLResponse:
    if not is_authenticated():
        return HTMLResponse(status_code=302, headers={"Location": "/login"})
    rev_query = f"?rev={rev}" if rev else ""
    pdf_url = f"/api/invoices/{invoice_id}/pdf{rev_query}"
    html = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Invoice {invoice_id}</title>
        <style>
          :root {{
            color-scheme: dark;
          }}
          body {{
            margin: 0;
            font-family: "Inter", "Segoe UI", system-ui, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
          }}
          .viewer-shell {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 16px;
          }}
          .viewer-header {{
            font-size: 14px;
            color: #fbbf24;
          }}
          #viewer {{
            width: 100%;
            height: 80vh;
            min-height: 70vh;
            max-height: 85vh;
            overflow: auto;
            background: #111827;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 12px;
          }}
          .page {{
            margin: 0 auto 16px auto;
            border-radius: 8px;
            background: white;
            border: 1px solid rgba(2, 6, 23, 0.18);
          }}
          .status {{
            font-size: 13px;
            color: #94a3b8;
          }}
          @media (max-width: 640px) {{
            .viewer-shell {{
              padding: 12px;
            }}
            #viewer {{
              height: 75vh;
              min-height: 70vh;
            }}
          }}
        </style>
        <script src="/static/pdfjs/pdf.min.js"></script>
      </head>
      <body>
        <div class="viewer-shell">
          <div class="viewer-header">Invoice PDF preview</div>
          <div id="viewer"></div>
          <div id="status" class="status">Loading PDF…</div>
        </div>
        <script>
          const pdfUrl = {json.dumps(pdf_url)};
          const viewer = document.getElementById("viewer");
          const status = document.getElementById("status");

          function waitForPdfJs() {{
            return new Promise((resolve, reject) => {{
              if (window.pdfjsLib) {{
                return resolve();
              }}
              if (window.__pdfjsLoadPromise) {{
                return window.__pdfjsLoadPromise.then(resolve).catch(reject);
              }}
              const start = Date.now();
              const timer = setInterval(() => {{
                if (window.pdfjsLib) {{
                  clearInterval(timer);
                  resolve();
                }} else if (Date.now() - start > 8000) {{
                  clearInterval(timer);
                  reject(new Error("PDF.js failed to load"));
                }}
              }}, 100);
            }});
          }}

          function clearViewer() {{
            viewer.innerHTML = "";
          }}

          function renderPage(page, scale) {{
            const viewport = page.getViewport({{ scale }});
            const canvas = document.createElement("canvas");
            const context = canvas.getContext("2d");
            const outputScale = window.devicePixelRatio || 1;
            canvas.width = Math.floor(viewport.width * outputScale);
            canvas.height = Math.floor(viewport.height * outputScale);
            canvas.style.width = Math.floor(viewport.width) + "px";
            canvas.style.height = Math.floor(viewport.height) + "px";
            canvas.className = "page";
            const renderContext = {{
              canvasContext: context,
              viewport: viewport,
              transform: outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null,
            }};
            return page.render(renderContext).promise.then(() => {{
              viewer.appendChild(canvas);
            }});
          }}

          function renderDocument(pdf) {{
            clearViewer();
            status.textContent = "Loaded " + pdf.numPages + " page" + (pdf.numPages === 1 ? "" : "s");
            const containerWidth = viewer.clientWidth - 24;
            const pagePromises = [];
            for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber++) {{
              pagePromises.push(
                pdf.getPage(pageNumber).then((page) => {{
                  const viewport = page.getViewport({{ scale: 1 }});
                  const scale = containerWidth / viewport.width;
                  return renderPage(page, scale);
                }})
              );
            }}
            return Promise.all(pagePromises);
          }}

          waitForPdfJs()
            .then(() => {{
              window.pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/pdfjs/pdf.worker.min.js";
              return window.pdfjsLib.getDocument(pdfUrl).promise;
            }})
            .then((pdf) => renderDocument(pdf))
            .catch((error) => {{
              console.error(error);
              status.textContent = "Failed to load PDF.";
            }});

          window.addEventListener("resize", () => {{
            if (!window.pdfjsLib || !viewer.firstChild) {{
              return;
            }}
            window.pdfjsLib.getDocument(pdfUrl).promise.then((pdf) => renderDocument(pdf));
          }});
        </script>
      </body>
    </html>
    """
    return HTMLResponse(html)


def set_page(name: str):
    app.storage.user["page"] = name
    ui.navigate.to("/")


@app.get("/api/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, rev: str | None = None):
    if not require_auth():
        raise HTTPException(status_code=401, detail="Unauthorized")

    with get_session() as session:
        user_id = get_current_user_id(session)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Unauthorized")

        invoice = session.get(Invoice, int(invoice_id))
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        customer = session.get(Customer, int(invoice.customer_id)) if invoice.customer_id else None
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        company = session.get(Company, int(customer.company_id)) if customer.company_id else None
        if not company or company.user_id != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        revision = int(invoice.revision_nr or 0)
        cache_key: _CACHE_KEY_TYPE = (int(invoice.id), revision)
        cached = _get_cached_pdf(cache_key)
        if cached is not None:
            return Response(content=cached, media_type="application/pdf")

        pdf_bytes: bytes | None = None
        if invoice.pdf_filename:
            pdf_path = invoice.pdf_filename
            if not os.path.isabs(pdf_path) and not str(pdf_path).startswith("storage/"):
                pdf_path = f"storage/invoices/{pdf_path}"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as handle:
                    pdf_bytes = handle.read()
        if pdf_bytes is None:
            pdf_bytes = render_invoice_to_pdf_bytes(invoice, company=company, customer=customer)
            if isinstance(pdf_bytes, bytearray):
                pdf_bytes = bytes(pdf_bytes)
            if not isinstance(pdf_bytes, bytes):
                raise HTTPException(status_code=500, detail="Invalid PDF output")
            filename = (
                os.path.basename(invoice.pdf_filename)
                if invoice.pdf_filename
                else (build_invoice_filename(company, invoice, customer) if invoice.nr else "rechnung.pdf")
            )
            pdf_path = f"storage/invoices/{filename}"
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            with open(pdf_path, "wb") as handle:
                handle.write(pdf_bytes)

            invoice.pdf_filename = filename
            invoice.pdf_storage = "local"
            session.add(invoice)
            session.commit()

        _store_cached_pdf(cache_key, pdf_bytes)
        return Response(content=pdf_bytes, media_type="application/pdf")


def _avatar_initials(identifier: str | None) -> str:
    if not identifier:
        return "U"
    cleaned = identifier.strip()
    if "@" in cleaned:
        cleaned = cleaned.split("@", 1)[0]
    parts = [part for part in re.split(r"[\s._-]+", cleaned) if part]
    if not parts:
        return "U"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[1][0]}".upper()


def _active_company_name() -> str | None:
    with get_session() as session:
        user_id = get_current_user_id(session)
        if not user_id:
            return None
        company = _resolve_active_company(session, user_id)
        name = getattr(company, "name", "") if company else ""
        return name.strip() or None


def _is_owner_user() -> bool:
    with get_session() as session:
        user_id = get_current_user_id(session)
        if not user_id:
            return False
        user = session.get(User, int(user_id))
        email = (user.email or "").strip().lower() if user else ""
        return email == get_owner_email()


def _page_title(page: str | None) -> str:
    titles = {
        "dashboard": "Dashboard",
        "invoices": "Invoices",
        "documents": "Documents",
        "exports": "Exports",
        "customers": "Customers",
        "customer_new": "New customer",
        "customer_detail": "Customer detail",
        "invoice_create": "Invoice editor",
        "invoice_detail": "Invoice detail",
        "expenses": "Expenses",
        "settings": "Settings",
    }
    return titles.get(page or "", "Invoices")

def _n8n_documents_today_count() -> int:
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    try:
        with get_session() as session:
            stmt = select(Document.id).where(
                Document.source.in_(["n8n", "N8N"]),
                Document.created_at >= start,
                Document.created_at < end,
            )
            return len(session.exec(stmt).all())
    except Exception:
        return 0


_LAYOUT = {
    "app_root": f"w-full min-h-screen {STYLE_BG}",
    "shell_row": "w-full min-h-screen items-start",
    "sidebar": (
        "fixed left-6 top-6 bottom-6 w-20 rounded-3xl bg-white border border-slate-200 "
        "shadow-sm items-center py-6 gap-5 z-40"
    ),
    "nav_sep": "w-8 h-px bg-slate-200",
    "nav_btn_base": (
        "w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-150 "
        "border border-transparent"
    ),
    "nav_btn_active": "text-amber-500 border-amber-200 bg-amber-50",
    "nav_btn_inactive": "text-slate-300 hover:text-amber-500 hover:border-amber-200 hover:bg-amber-50",
    "main": "flex-1 w-full relative px-4 pb-8 md:pl-28 md:pr-6",
    "topbar": "w-full items-center gap-4 pt-6 pb-4 sticky top-0 z-30 bg-slate-50/80 backdrop-blur",
    "topbar_left": "flex-1 items-center gap-4",
    "topbar_right": "flex-1 items-center justify-end gap-2",
    "icon_btn": f"{STYLE_TAP_TARGET} text-slate-300 hover:text-amber-500",
    "mobile_menu_btn": f"md:hidden {STYLE_TAP_TARGET} text-slate-400 hover:text-amber-500",
    "mobile_drawer": "md:hidden",
    "mobile_nav": "w-full gap-2 p-4",
    "mobile_nav_btn": f"w-full justify-start text-slate-700 {STYLE_TAP_TARGET}",
    "sidebar_logo": "ff-sidebar-logo w-11 h-11 rounded-none object-contain",
    "header_search": f"{STYLE_INPUT} w-72",
    "new_invoice_btn": f"{STYLE_BTN_ACCENT} w-[150px]",
    "menu_wide": "min-w-[240px]",
    "menu": "min-w-[220px]",
    "menu_meta": "text-xs text-slate-600 px-3 pt-2",
    "menu_meta_company": "text-sm text-slate-600 px-3 pb-2",
    "content": "w-full",
    "user_btn": f"opacity-100 w-10 h-10 rounded-xl bg-white border border-slate-200 hover:bg-slate-50 {STYLE_TAP_TARGET}",
    "user_initials": "text-xs font-semibold text-slate-900",
    "logout_item": "text-rose-600",
}


def layout_wrapper(content_func):
    identifier = app.storage.user.get("auth_user")
    initials = _avatar_initials(identifier)
    company_name = _active_company_name()
    company_logo_url = "/static/Logo-fixundfertig.svg"
    n8n_today_count = _n8n_documents_today_count()
    is_owner = _is_owner_user()
    current_page = app.storage.user.get("page", "dashboard")

    with ui.element("div").classes(_LAYOUT["app_root"]):
        mobile_drawer = ui.drawer().classes(_LAYOUT["mobile_drawer"])
        with mobile_drawer:
            with ui.column().classes(_LAYOUT["mobile_nav"]):

                def mobile_nav_item(label: str, target: str, icon: str) -> None:
                    def handle_nav() -> None:
                        set_page(target)
                        mobile_drawer.close()

                    ui.button(label, icon=icon, on_click=handle_nav).props("flat no-caps").classes(
                        _LAYOUT["mobile_nav_btn"]
                    )

                mobile_nav_item("Dashboard", "dashboard", "dashboard")
                mobile_nav_item("Invoices", "invoices", "receipt_long")
                mobile_nav_item("Documents", "documents", "description")
                mobile_nav_item("Customers", "customers", "groups")
                mobile_nav_item("Ledger", "ledger", "account_balance")

        with ui.row().classes(_LAYOUT["shell_row"]):
            # Sidebar
            with ui.column().classes(f'{_LAYOUT["sidebar"]} hidden md:flex'):
                ui.image(company_logo_url).classes(_LAYOUT["sidebar_logo"])

                def nav_item(label: str, target: str, icon: str) -> None:
                    active = app.storage.user.get("page", "dashboard") == target
                    cls = (
                        f'{_LAYOUT["nav_btn_base"]} {_LAYOUT["nav_btn_active"]}'
                        if active
                        else f'{_LAYOUT["nav_btn_base"]} {_LAYOUT["nav_btn_inactive"]}'
                    )
                    with ui.button(icon=icon, on_click=lambda t=target: set_page(t)).props(
                        "flat no-caps no-ripple"
                    ).classes(cls):
                        ui.tooltip(label)

                nav_item("Dashboard", "dashboard", "dashboard")
                ui.element("div").classes(_LAYOUT["nav_sep"])
                nav_item("Invoices", "invoices", "receipt_long")
                nav_item("Documents", "documents", "description")
                nav_item("Ledger", "ledger", "account_balance")
                nav_item("Exports", "exports", "file_download")
                ui.element("div").classes(_LAYOUT["nav_sep"])
                nav_item("Customers", "customers", "groups")
                if is_owner:
                    nav_item("Einladungen", "invites", "mail")

            # Main content
            with ui.column().classes(_LAYOUT["main"]):

                def handle_logout() -> None:
                    clear_auth_session()
                    ui.navigate.to("/login")

                def open_ledger_search(query: str) -> None:
                    app.storage.user["ledger_search_query"] = (query or "").strip()
                    app.storage.user["page"] = "ledger"
                    ui.navigate.to("/")

                with ui.row().classes(_LAYOUT["topbar"]):
                    with ui.row().classes(_LAYOUT["topbar_left"]):
                        ui.button(icon="menu", on_click=mobile_drawer.toggle).props("flat round").classes(
                            _LAYOUT["mobile_menu_btn"]
                        )
                        ui.input(
                            "Search transactions",
                            on_change=lambda e: open_ledger_search(e.value or ""),
                        ).props("outlined dense").classes(_LAYOUT["header_search"])
                    with ui.row().classes(_LAYOUT["topbar_right"]):
                        with ui.button(icon="notifications").props("flat round").classes(
                            _LAYOUT["icon_btn"]
                        ):
                            with ui.menu().classes(_LAYOUT["menu_wide"]):
                                notifications: list[str] = []
                                if n8n_today_count:
                                    notifications.append(
                                        f"{n8n_today_count} neue N8N-Dokumente heute"
                                    )
                                if notifications:
                                    for entry in notifications:
                                        ui.item(entry)
                                else:
                                    ui.item("Keine neuen Benachrichtigungen.").classes(STYLE_TEXT_MUTED)
                        ui.button(
                            "New Invoice",
                            on_click=lambda: _open_invoice_editor(None),
                        ).props("flat no-caps").classes(_LAYOUT["new_invoice_btn"])
                        with ui.button().props("flat no-caps").classes(_LAYOUT["user_btn"]):
                            ui.label(initials).classes(_LAYOUT["user_initials"])
                            with ui.menu().classes(_LAYOUT["menu"]):
                                if identifier:
                                    ui.label(identifier).classes(_LAYOUT["menu_meta"])
                                if company_name:
                                    ui.label(company_name).classes(_LAYOUT["menu_meta_company"])
                                ui.separator().classes("my-1")
                                ui.item("Settings", on_click=lambda: ui.navigate.to("/settings"))
                                ui.item("Logout", on_click=handle_logout).classes(_LAYOUT["logout_item"])

                with ui.element("div").classes(_LAYOUT["content"]):
                    content_func()


@ui.page("/")
def index():
    apply_global_ui_theme()
    if not require_auth():
        return

    app.add_static_files("/storage", "storage")

    # Ensure company exists
    with get_session() as session:
        user_id = get_current_user_id(session)
        if user_id is None:
            clear_auth_session()
            ui.navigate.to("/login")
            return
        companies = list_companies(session, user_id)
        if not companies:
            get_primary_company(session, user_id)

    page = app.storage.user.get("page", "dashboard")
    if page in {"home", "todos"}:
        page = "dashboard"
        app.storage.user["page"] = page

    def content():
        with get_session() as session:
            user_id = get_current_user_id(session)
            if user_id is None:
                clear_auth_session()
                ui.navigate.to("/login")
                return

            companies = list_companies(session, user_id)

            # ✅ ACTIVE COMPANY SELECTION (correct indentation)
            active_id = app.storage.user.get("active_company_id")
            try:
                active_id = int(active_id) if active_id is not None else None
            except Exception:
                active_id = None

            comp = None
            if active_id:
                comp = next((c for c in companies if int(c.id or 0) == active_id), None)

            if not comp:
                comp = companies[0] if companies else get_primary_company(session, user_id)

            if comp and comp.id:
                app.storage.user["active_company_id"] = int(comp.id)

            # Full-width flows (editor / detail)
            if page == "invoice_create":
                render_invoice_create(session, comp)
                return
            if page == "invoice_detail":
                render_invoice_detail(session, comp)
                return
            if page == "settings":
                render_settings(session, comp)
                return

            # Normal pages in container
            with ui.column().classes(STYLE_CONTAINER):
                if page == "dashboard":
                    render_dashboard(session, comp)
                elif page == "customers":
                    render_customers(session, comp)
                elif page == "customer_new":
                    render_customer_new(session, comp)
                elif page == "customer_detail":
                    customer_id = app.storage.user.get("customer_detail_id")
                    render_customer_detail(session, comp, customer_id)
                elif page == "invoices":
                    render_invoices(session, comp)
                elif page == "documents":
                    render_documents(session, comp)
                elif page == "expenses":
                    render_expenses(session, comp)
                elif page == "ledger":
                    render_ledger(session, comp)
                elif page == "invites":
                    render_invites(session, comp)
                elif page == "exports":
                    render_exports(session, comp)
                else:
                    render_invoices(session, comp)

    layout_wrapper(content)


@ui.page("/settings")
def settings_page():
    apply_global_ui_theme()
    if not require_auth():
        return
    app.storage.user["page"] = "settings"
    ui.navigate.to("/")


# ... (Code davor bleibt gleich)

# Pytest helpers: allow setting `app.storage.user` without an active request.
if _IS_PYTEST:
    _dummy_request = type("DummyRequest", (), {"session": {"id": "pytest"}})()
    request_contextvar.set(_dummy_request)
    if "pytest" not in app.storage._users:
        app.storage._users["pytest"] = PseudoPersistentDict()
        app.storage._users["pytest"].initialize_sync()

# 2. Der Start-Block
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="FixundFertig",
        host="0.0.0.0",      # <--- WICHTIG: Damit Docker von außen draufkommt
        port=8000,           # <--- WICHTIG: Muss zum Dockerfile/Docker-Compose passen (war 8080)
        language="de",
        storage_secret=storage_secret,
        favicon="/static/Logo-fixundfertig-01.ico",
    )
