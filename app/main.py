# =========================
# APP/MAIN.PY (REPLACE FULL FILE)
# =========================

import base64
import hashlib
import hmac
import importlib.util
import json
import mimetypes
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import HTTPException, Response, UploadFile, File, Form, Header, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from nicegui import ui, app
from sqlmodel import select

from env import load_env
from auth_guard import clear_auth_session, require_auth
from data import Company, Customer, Document, DocumentMeta, Invoice, WebhookEvent, get_session
from renderer import render_invoice_to_pdf_bytes
from styles import C_BG, C_BTN_SEC, C_CONTAINER, C_NAV_ITEM, C_NAV_ITEM_ACTIVE
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
    render_ledger,
    render_exports,
)
from pages._shared import get_current_user_id, get_primary_company, list_companies
from services.blob_storage import blob_storage, build_document_key
from services.documents import (
    build_document_record,
    build_display_title,
    document_matches_filters,
    ensure_document_dir,
    normalize_keywords,
    resolve_document_path,
    safe_filename,
    set_document_storage_path,
    serialize_document,
    validate_document_upload,
)
from storage.service import save_upload_bytes

_CACHE_TTL_SECONDS = 300
_CACHE_MAXSIZE = 256
_CACHE_KEY_TYPE = tuple[int, int]
_cachetools_spec = importlib.util.find_spec("cachetools")
if _cachetools_spec is not None:
    from cachetools import TTLCache
    _invoice_pdf_cache = TTLCache(maxsize=_CACHE_MAXSIZE, ttl=_CACHE_TTL_SECONDS)
else:
    _invoice_pdf_cache: dict[_CACHE_KEY_TYPE, tuple[float, bytes]] = {}


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

load_env()
app.add_static_files("/static", str(Path(__file__).resolve().parent / "static"))


def _require_api_auth() -> None:
    if not app.storage.user.get("auth_user"):
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


@app.post("/api/webhooks/n8n/ingest")
async def n8n_ingest(request: Request):
    raw_body = await request.body()
    timestamp_header = (request.headers.get("X-Timestamp") or "").strip()
    signature = (request.headers.get("X-Signature") or "").strip()

    if not timestamp_header or not signature:
        raise HTTPException(status_code=401, detail="Missing signature headers")

    try:
        timestamp = int(timestamp_header)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp")

    drift = abs(int(time.time()) - timestamp)
    if drift > 300:
        raise HTTPException(status_code=401, detail="Timestamp drift too large")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload structure")

    event_id = str(payload.get("event_id") or "").strip()
    company_id_raw = payload.get("company_id")
    file_base64 = payload.get("file_base64")
    if not event_id or not company_id_raw or not file_base64:
        raise HTTPException(status_code=400, detail="Missing required payload fields")

    try:
        company_id = int(company_id_raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid company_id")

    with get_session() as session:
        company = session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        if not bool(getattr(company, "n8n_enabled", False)):
            raise HTTPException(status_code=403, detail="n8n is disabled")
        secret = (getattr(company, "n8n_secret", "") or "").strip()
        if not secret:
            raise HTTPException(status_code=403, detail="Missing n8n secret")

        signed_payload = f"{timestamp_header}.".encode("utf-8") + raw_body
        expected_signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

        existing_event = session.exec(
            select(WebhookEvent).where(WebhookEvent.event_id == event_id)
        ).first()
        if existing_event:
            raise HTTPException(status_code=409, detail="Duplicate event")

        file_payload = str(file_base64)
        if "," in file_payload and "base64" in file_payload.split(",", 1)[0]:
            file_payload = file_payload.split(",", 1)[1]
        try:
            file_bytes = base64.b64decode(file_payload, validate=True)
        except Exception:
            try:
                file_bytes = base64.b64decode(file_payload)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid file_base64")

        file_name = (payload.get("file_name") or payload.get("filename") or "").strip()
        if not file_name:
            file_name = f"document_{event_id}.bin"
        original_filename = file_name
        safe_name = safe_filename(file_name)

        ext = os.path.splitext(safe_name)[1].lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"
        mime_type = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "png": "image/png",
            "txt": "text/plain",
        }.get(ext, "application/octet-stream")

        document = build_document_record(
            company_id,
            original_filename,
            mime_type=mime_type,
            size_bytes=len(file_bytes),
            source="n8n",
            doc_type=ext,
        )
        document.storage_path = storage_info["path"]
        session.add(document)
        session.commit()
        session.refresh(document)

        set_document_storage_path(document)
        ensure_document_dir(company_id, int(document.id))
        storage_path = resolve_document_path(document.storage_path)
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)

        try:
            with open(storage_path, "wb") as handle:
                handle.write(file_bytes)
        except OSError as exc:
            session.delete(document)
            session.commit()
            raise HTTPException(status_code=500, detail=f"Failed to store file: {exc}") from exc

        document.size_bytes = len(file_bytes)
        session.add(document)

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
        session.add(
            DocumentMeta(
                document_id=int(document.id or 0),
                source="n8n",
                payload_json=json.dumps({"payload": payload, "sha256": sha256}, ensure_ascii=False),
            )
        )
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


@app.post("/api/webhooks/n8n/upload")
async def n8n_upload(
    file: UploadFile = File(...),
    payload_json: str = Form(...),
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
    x_n8n_secret: str | None = Header(None, alias="X-N8N-Secret"),
    file_name: str | None = Form(None),
    title: str | None = Form(None),
    description: str | None = Form(None),
    vendor: str | None = Form(None),
    doc_date: str | None = Form(None),
    amount_total: str | None = Form(None),
    currency: str | None = Form(None),
    keywords: str | None = Form(None),
) -> Response:
    if not x_company_id or not x_n8n_secret:
        raise HTTPException(status_code=401, detail="Missing auth headers")
    try:
        company_id = int(x_company_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid company id")

    try:
        payload = json.loads(payload_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload_json")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload_json")
    extracted = payload.get("extracted") or {}
    if not isinstance(extracted, dict):
        extracted = {}

    raw_filename = (
        file_name
        or payload.get("file_name")
        or payload.get("filename")
        or payload.get("name")
        or file.filename
        or "document"
    )
    safe_name = safe_filename(str(raw_filename))
    is_bnh = str(raw_filename).lower().endswith(".bnh") or (file.filename or "").lower().endswith(".bnh")
    if safe_name.lower().endswith(".bnh"):
        is_bnh = True
    if is_bnh and not safe_name.lower().endswith(".bnh"):
        safe_name = f"{safe_name}.bnh"

    file_bytes = await file.read()
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    mime = (file.content_type or "").strip()
    if is_bnh:
        mime = "application/octet-stream"
    if not mime:
        ext = os.path.splitext(safe_name)[1].lower().lstrip(".")
        mime = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
        }.get(ext, "application/octet-stream")

    vendor_value = (vendor or extracted.get("vendor") or payload.get("vendor") or "").strip()
    doc_date_value = (doc_date or extracted.get("doc_date") or payload.get("doc_date") or "").strip() or None
    amount_value = _parse_optional_float(
        amount_total if amount_total is not None else extracted.get("amount_total") or payload.get("amount_total")
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
    description_value = (description or extracted.get("summary") or payload.get("summary") or "").strip()

    with get_session() as session:
        company = session.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        if not bool(getattr(company, "n8n_enabled", False)):
            raise HTTPException(status_code=403, detail="n8n is disabled")
        secret = (getattr(company, "n8n_secret", "") or "").strip()
        if not secret or not hmac.compare_digest(secret, x_n8n_secret):
            raise HTTPException(status_code=401, detail="Invalid secret")

        existing = session.exec(
            select(Document).where(
                Document.company_id == company_id,
                Document.sha256 == sha256,
                Document.source == "N8N",
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
        document = Document(
            company_id=company_id,
            filename=safe_name,
            storage_key="pending",
            original_filename=str(raw_filename),
            mime_type=mime,
            size_bytes=len(file_bytes),
            source="N8N",
            doc_type=ext,
            storage_path="",
            mime=mime,
            size=len(file_bytes),
            sha256=sha256,
            title=title_value,
            description=description_value,
            vendor=vendor_value,
            doc_date=doc_date_value,
            amount_total=amount_value,
            currency=currency_value,
            keywords_json=normalize_keywords(keywords_value),
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        storage_key = build_document_key(company_id, int(document.id or 0), safe_name)
        blob_storage().put_bytes(storage_key, file_bytes, mime)
        document.storage_key = storage_key
        document.storage_path = storage_key
        session.add(document)
        session.commit()

        return JSONResponse(
            status_code=201,
            content={
                "ok": True,
                "duplicate": False,
                "document_id": int(document.id or 0),
            },
        )


@app.get("/api/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, rev: str | None = None) -> Response:
    _require_api_auth()
    with get_session() as session:
        invoice = session.get(Invoice, invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        customer = session.get(Customer, invoice.customer_id) if invoice.customer_id else None
        company = None
        if customer and customer.company_id:
            company = session.get(Company, customer.company_id)
        if not company:
            company = session.exec(select(Company)).first() or Company()

        pdf_path = _resolve_invoice_pdf_path(invoice.pdf_filename)
        if pdf_path and pdf_path.exists():
            return Response(pdf_path.read_bytes(), media_type="application/pdf")

        if invoice.pdf_bytes:
            pdf_bytes = invoice.pdf_bytes
        else:
            pdf_bytes = render_invoice_to_pdf_bytes(invoice, company)
        if isinstance(pdf_bytes, bytearray):
            pdf_bytes = bytes(pdf_bytes)
        return Response(pdf_bytes, media_type="application/pdf")


@app.post("/api/documents/upload")
async def document_upload(
    company_id: int = Form(...),
    file: UploadFile = File(...),
) -> dict:
    _require_api_auth()
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

        try:
            document = build_document_record(
                int(company.id),
                filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                source="MANUAL",
                doc_type=ext,
            )
            document.mime = mime_type
            document.size = size_bytes
            document.sha256 = sha256
            session.add(document)
            session.flush()

            storage_key = build_document_key(int(company.id), int(document.id), filename)
            document.storage_key = storage_key
            document.storage_path = storage_key

            blob_storage().put_bytes(storage_key, contents, mime_type)
            session.commit()
            session.refresh(document)
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

        storage_path = document_storage_path(int(document.company_id), document.storage_key)
        if not storage_path or not os.path.exists(storage_path):
            raise HTTPException(status_code=404, detail="File not found")

        content_type = document.mime or "application/octet-stream"
        if content_type.endswith("/pdf"):
            disposition = "inline"
        else:
            disposition = "attachment"
        headers = {
            "Content-Disposition": f'{disposition}; filename="{document.original_filename or "document"}"'
        }
        return FileResponse(storage_path, media_type=content_type, headers=headers)


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

        storage_path = document_storage_path(int(document.company_id), document.storage_key)
        if storage_path and os.path.exists(storage_path):
            try:
                os.remove(storage_path)
            except OSError:
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
    if not app.storage.user.get("auth_user"):
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
            color-scheme: light;
          }}
          body {{
            margin: 0;
            font-family: "Inter", "Segoe UI", system-ui, sans-serif;
            background: #f8fafc;
          }}
          .viewer-shell {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 16px;
          }}
          .viewer-header {{
            font-size: 14px;
            color: #475569;
          }}
          #viewer {{
            width: 100%;
            height: 80vh;
            min-height: 70vh;
            max-height: 85vh;
            overflow: auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
            padding: 12px;
          }}
          .page {{
            margin: 0 auto 16px auto;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
            border-radius: 8px;
            background: white;
          }}
          .status {{
            font-size: 13px;
            color: #64748b;
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
def invoice_pdf(invoice_id: int):
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


def layout_wrapper(content_func):
    # App shell with left sidebar
    with ui.element("div").classes(C_BG + " w-full"):
        with ui.row().classes("w-full min-h-screen"):
            # Sidebar
            with ui.column().classes(
                "w-[260px] bg-white border-r border-slate-200 p-4 gap-6 sticky top-0 h-screen overflow-y-auto"
            ):
                with ui.row().classes("items-center gap-2 px-2"):
                    ui.label("FixundFertig").classes("text-lg font-bold text-slate-900")
                ui.separator().classes("opacity-60")

                def nav_section(title: str, items: list[tuple[str, str]]):
                    ui.label(title).classes(
                        "text-xs font-semibold text-slate-400 uppercase tracking-wider px-2 mt-1"
                    )
                    with ui.column().classes("gap-1 mt-1"):
                        for label, target in items:
                            active = app.storage.user.get("page", "invoices") == target
                            cls = C_NAV_ITEM_ACTIVE if active else C_NAV_ITEM
                            ui.button(
                                label,
                                on_click=lambda t=target: set_page(t),
                            ).props("flat").classes(f"w-full justify-start normal-case {cls}")

                nav_section("Workspace", [("Dashboard", "dashboard")])
                nav_section(
                    "Billing",
                    [
                        ("Rechnungen", "invoices"),
                        ("Dokumente", "documents"),
                        ("Finanzen", "ledger"),
                        ("Exporte", "exports"),
                    ],
                )
                nav_section("CRM", [("Kunden", "customers")])
                nav_section("Settings", [("Einstellungen", "settings")])

            # Main content
            with ui.column().classes("flex-1 w-full"):
                with ui.row().classes("w-full justify-end px-6 py-4"):

                    def handle_logout() -> None:
                        clear_auth_session()
                        ui.navigate.to("/login")

                    ui.button("Logout", on_click=handle_logout).classes(C_BTN_SEC)
                content_func()


@ui.page("/")
def index():
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

    page = app.storage.user.get("page", "invoices")

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
            with ui.column().classes(C_CONTAINER):
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
                elif page == "exports":
                    render_exports(session, comp)
                else:
                    render_invoices(session, comp)

    layout_wrapper(content)


storage_secret = os.getenv("STORAGE_SECRET", "secret2026")
ui.run(
    title="FixundFertig",
    port=8080,
    language="de",
    storage_secret=storage_secret,
    favicon="🚀",
)
