"""Invoice viewer and PDF endpoints extracted from main.py."""
from __future__ import annotations

import importlib.util
import json
import os

from fastapi import HTTPException, Response
from fastapi.responses import HTMLResponse
from nicegui import app

from auth_guard import is_authenticated, require_auth
from data import Company, Customer, Invoice, User, get_session
from pages._shared import get_current_user_id
from renderer import render_invoice_to_pdf_bytes
from invoice_numbering import build_invoice_filename
from services.auth import validate_readonly_share_token

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
    cached = _invoice_pdf_cache.get(cache_key)
    if cached is None:
        return None
    _ts, data = cached
    return data


def _store_cached_pdf(cache_key: _CACHE_KEY_TYPE, payload: bytes) -> None:
    import time
    _invoice_pdf_cache[cache_key] = (time.monotonic(), payload)


@app.get("/share/read/{token}")
def readonly_share_entry(token: str) -> Response:
    token_value = (token or "").strip()
    payload = validate_readonly_share_token(token_value)
    if not payload:
        raise HTTPException(status_code=400, detail="Invalid or expired share token")
    scope = payload.get("scope") or {}
    with get_session() as session:
        user = session.get(User, int(payload.get("user_id") or 0))
    if user:
        app.storage.user["auth_user"] = user.email or user.username
    app.storage.user["readonly_mode"] = True
    app.storage.user["readonly_scope"] = scope
    invoice_id = scope.get("invoice_id")
    if invoice_id:
        return Response(status_code=302, headers={"Location": f"/viewer/invoice/{int(invoice_id)}?share_token={token_value}"})
    app.storage.user["page"] = "dashboard"
    return Response(status_code=302, headers={"Location": "/"})


@app.get("/viewer/invoice/{invoice_id}", response_class=HTMLResponse)
def invoice_viewer(invoice_id: int, rev: str | None = None, share_token: str | None = None) -> HTMLResponse:
    token_value = (share_token or "").strip()
    payload = validate_readonly_share_token(token_value) if token_value else None
    if payload:
        scope = payload.get("scope") or {}
        token_invoice_id = int(scope.get("invoice_id") or 0)
        if token_invoice_id != int(invoice_id):
            raise HTTPException(status_code=403, detail="Forbidden")
    elif not is_authenticated():
        return HTMLResponse(status_code=302, headers={"Location": "/login"})
    rev_query = f"?rev={rev}" if rev else ""
    token_query = f"share_token={token_value}" if token_value else ""
    query_parts = [part for part in (rev_query.lstrip("?"), token_query) if part]
    query = f"?{'&'.join(query_parts)}" if query_parts else ""
    pdf_url = f"/api/invoices/{invoice_id}/pdf{query}"
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


@app.get("/api/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: int, rev: str | None = None, share_token: str | None = None):
    token_value = (share_token or "").strip()
    payload = validate_readonly_share_token(token_value) if token_value else None
    readonly_user_id = int(payload.get("user_id") or 0) if payload else None
    if payload:
        scope = payload.get("scope") or {}
        token_invoice_id = int(scope.get("invoice_id") or 0)
        if token_invoice_id != int(invoice_id):
            raise HTTPException(status_code=403, detail="Forbidden")
    elif not require_auth():
        raise HTTPException(status_code=401, detail="Unauthorized")

    with get_session() as session:
        user_id = readonly_user_id if readonly_user_id else get_current_user_id(session)
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
