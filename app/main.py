# =========================
# APP/MAIN.PY (REPLACE FULL FILE)
# =========================

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, Response
from nicegui import ui, app
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlmodel import select

from env import load_env
from auth_guard import clear_auth_session, require_auth
from data import Company, Customer, Invoice, get_session
from renderer import render_invoice_to_pdf_bytes
from styles import C_BG, C_CONTAINER, C_NAV_ITEM, C_NAV_ITEM_ACTIVE
from pages import (
    render_dashboard,
    render_customers,
    render_customer_new,
    render_customer_detail,
    render_invoices,
    render_invoice_create,
    render_invoice_detail,
    render_expenses,
    render_settings,
    render_ledger,
    render_exports,
)
from pages._shared import get_current_user_id, get_primary_company, list_companies

load_env()
app.add_static_files("/static", "app/static")


def _require_api_auth() -> None:
    if not app.storage.user.get("auth_user"):
        raise HTTPException(status_code=401, detail="Not authenticated")


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
