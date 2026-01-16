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
from urllib.request import Request, urlopen

from fastapi import HTTPException, Request, Response, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from nicegui import ui, app
from sqlmodel import select

from env import load_env
from auth_guard import clear_auth_session, require_auth
from data import Company, Customer, Document, Invoice, get_session
from models.document import DocumentSource, normalize_keywords
from renderer import render_invoice_to_pdf_bytes
from styles import C_BG, C_CONTAINER, C_NAV_ITEM, C_NAV_ITEM_ACTIVE
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
from services.documents import (
    build_document_record,
    compute_sha256_bytes,
    document_matches_filters,
    resolve_document_path,
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
    request = Request(
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
        mime_type = (payload.get("mime") or payload.get("mime_type") or "").strip()
        storage_info = save_upload_bytes(company_id, file_name, file_bytes, mime_type)
        ext = os.path.splitext(file_name)[1].lower().lstrip(".")
        if ext == "jpeg":
            ext = "jpg"

        document = build_document_record(
            company_id,
            file_name,
            mime_type=storage_info["mime"],
            size_bytes=storage_info["size"],
            source="n8n",
            doc_type=ext,
            original_filename=file_name,
        )
        document.storage_path = storage_info["path"]
        session.add(document)
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

        storage_info = save_upload_bytes(int(company.id), filename, contents, mime_type)
        document = build_document_record(
            int(company.id),
            filename,
            mime_type=storage_info["mime"],
            size_bytes=storage_info["size"],
            source="manual",
            doc_type=ext,
            original_filename=filename,
        )
        document.storage_path = storage_info["path"]
        session.add(document)
        session.commit()
        session.refresh(document)
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

                    ui.button("Logout", on_click=handle_logout).props("flat").classes(
                        "text-slate-500 hover:text-slate-900"
                    )
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


ui.run(title="FixundFertig", port=8080, language="de", storage_secret="secret2026", favicon="🚀")
