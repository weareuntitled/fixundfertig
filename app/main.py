# =========================
# APP/MAIN.PY (REPLACE FULL FILE)
# =========================

import hashlib
import importlib.util
import logging
import re
import os
import time
from threading import Lock
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException, Response, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse
from nicegui import ui, app, helpers
from nicegui.storage import Storage, PseudoPersistentDict, request_contextvar
from sqlmodel import select
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from env import load_env

# Load ".env" before importing modules that read env vars at import time.
load_env()

from logging_setup import setup_logging

setup_logging()

from auth_guard import clear_auth_session, is_authenticated, require_auth, set_request_for_context
from data import Company, Customer, Document, Invoice, User, get_session
from styles import STYLE_BG, STYLE_CONTAINER, STYLE_INPUT, STYLE_TAP_TARGET, STYLE_TEXT_MUTED
from ui_theme import apply_global_ui_theme
from ui_components import ff_btn_primary, ff_card, ff_icon_button
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
from pages._shared import (
    get_current_user_id,
    get_primary_company,
    go_app_page,
    list_companies,
    _open_invoice_editor,
    register_shell_navigate,
    app_shell_nav_items,
)
from services.blob_storage import blob_storage, build_document_key
from services.auth import ensure_owner_user, get_owner_email
from services.documents import (
    build_document_record,
    build_display_title,
    normalize_keywords,
    safe_filename,
    serialize_document,
    validate_document_upload,
)
logger = logging.getLogger(__name__)
_cachetools_spec = importlib.util.find_spec("cachetools")
if _cachetools_spec is not None:
    from cachetools import TTLCache

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
        hosts = list(explicit)
    else:
        hosts = []
        domain = (os.getenv("APP_DOMAIN") or "").strip()
        if domain:
            hosts.extend([domain, f"www.{domain}"])

        base_url = (os.getenv("APP_BASE_URL") or "").strip()
        if base_url:
            parsed = urlparse(base_url if "://" in base_url else f"https://{base_url}")
            if parsed.hostname:
                hosts.append(parsed.hostname)

        if not _IS_PROD:
            hosts.extend(["localhost", "127.0.0.1", "0.0.0.0"])

    # Allow localhost when explicitly requested (e.g. local Docker on port 3000)
    if (os.getenv("FF_ALLOW_LOCALHOST") or "").strip() == "1":
        hosts.extend(["localhost", "127.0.0.1"])

    # TestClient uses host "testserver"; always allow it under pytest even if FF_TRUSTED_HOSTS is set.
    if _IS_PYTEST:
        hosts.append("testserver")

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


class _RequestContextMiddleware:
    """Set current request in context so auth_guard can detect localhost for FF_NO_LOGIN_LOCAL."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            request = Request(scope, receive, send)
            set_request_for_context(request)
        await self.app(scope, receive, send)


_configure_security_middleware()
app.add_middleware(_RequestContextMiddleware)

from api import api_router  # noqa: E402  (after middleware so middleware applies to api routes too)
app.include_router(api_router)

import webhooks  # noqa: E402  (registers n8n webhook endpoints)
import viewer  # noqa: E402  (registers invoice viewer/PDF endpoints)

# ── React SPA mount (BEFORE NiceGUI so it takes priority) ──
from starlette.routing import Mount as _Mount
from starlette.staticfiles import StaticFiles as _StaticFiles
from starlette.responses import FileResponse as _FileResponse

_REACT_DIST = Path(__file__).resolve().parent / "static" / "frontend"
_REACT_INDEX = _REACT_DIST / "index.html"


class _ReactSPA(_StaticFiles):
    """Serves the React SPA: index.html for /app/*, static assets for /app/assets/*."""

    def __init__(self):
        directory = str(_REACT_DIST) if _REACT_DIST.is_dir() else str(Path(__file__).resolve().parent)
        super().__init__(directory=directory, html=True)

    async def get_response(self, path, scope):
        # For /app itself or /app/ with no file extension → serve index.html
        if not path or path == "" or (not "." in path.split("/")[-1]):
            if _REACT_INDEX.is_file():
                return _FileResponse(str(_REACT_INDEX))
        return await super().get_response(path, scope)


if _REACT_DIST.is_dir():
    app.mount("/static/frontend", _StaticFiles(directory=str(_REACT_DIST), html=True), name="react-static")
    # React SPA is now the primary UI — mount at root so all browser paths hit it.
    # API routes, static files, and favicon route are registered above and take priority.
    app.mount("/", _ReactSPA(), name="react-spa-root")


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



def _build_document_storage_path(
    company_id: int,
    document_id: int,
    filename: str,
    created_at: datetime | None,
) -> str:
    timestamp = created_at if isinstance(created_at, datetime) else datetime.utcnow()
    return build_document_key(company_id, document_id, filename, now=timestamp)


app.add_static_files("/static", str(Path(__file__).resolve().parent / "static"))
_FAVICON_PATH = Path(__file__).resolve().parent / "static" / "Logo-fixundfertig.svg"


@app.get("/favicon.ico")
def favicon_ico():
    """Avoid FileResponse edge cases in some environments; browsers follow redirect."""
    if not _FAVICON_PATH.is_file():
        raise HTTPException(status_code=404, detail="favicon not found")
    return RedirectResponse(url="/static/Logo-fixundfertig.svg", status_code=307)


if not _IS_PYTEST:
    try:
        ensure_owner_user()
    except Exception:
        logger.exception("Failed to ensure owner user")


def _require_api_auth() -> None:
    if not is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")


def _is_readonly_mode() -> bool:
    return bool(app.storage.user.get("readonly_mode"))


def _require_write_access() -> None:
    if _is_readonly_mode():
        raise HTTPException(status_code=403, detail="Read-only preview mode")


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


def _parse_optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    _require_write_access()
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


@app.get("/api/documents/upload")
def list_documents_upload_marker():
    """Marker — real upload endpoint follows below. This stub keeps route registration stable."""
    return Response(status_code=501, content="use POST /api/documents/upload")

# === Documents API: list, file, delete (moved to app/api/documents.py, see below) ===




_content_ref = None
_shell_sidebar_ref = None
_shell_mobile_nav_ref = None


def _sidebar_highlight_target(logical_page: str) -> str:
    """Which sidebar item should look active (sub-pages map to their section)."""
    if logical_page in ("invoice_create", "invoice_detail"):
        return "invoices"
    if logical_page in ("customer_new", "customer_detail"):
        return "customers"
    return logical_page


def _refresh_shell_nav() -> None:
    for ref in (_shell_sidebar_ref, _shell_mobile_nav_ref):
        if ref is None:
            continue
        try:
            ref.refresh()
        except Exception:
            pass


def set_page(name: str) -> None:
    """Switch logical page inside the shell and refresh only the content."""
    global _content_ref
    app.storage.user["page"] = name
    _refresh_shell_nav()
    ref = _content_ref
    if ref is not None:
        try:
            ref.refresh()
            return
        except Exception:
            # Fallback: full navigation if refreshable content is not available
            pass
    ui.navigate.to("/")


register_shell_navigate(set_page)


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
    "shell_row": "w-full min-h-screen flex flex-col md:flex-row items-start gap-6 px-4 md:px-6",
    # Desktop sidebar: use .ff-desktop-sidebar for guaranteed visibility on md+ (see styles.py).
    "sidebar": (
        "ff-desktop-sidebar rounded-lg bg-white/90 backdrop-blur-sm "
        "border border-slate-200/80 shadow-[0_1px_2px_rgba(0,0,0,0.04)] ring-1 ring-slate-900/[0.03] "
        "items-start py-3 px-2 gap-1 shrink-0"
    ),
    "nav_sep": "w-8 h-px bg-slate-100 mx-auto",
    "nav_btn_base": (
        "ff-nav-btn w-full h-7 rounded-md flex items-center justify-start gap-2 px-2 "
        "border border-transparent text-[12.5px] font-medium"
    ),
    "nav_btn_active": "ff-nav-active bg-indigo-600 text-white shadow-sm",
    "nav_btn_inactive": "text-slate-500 hover:text-slate-900 hover:bg-slate-100/80",
    "nav_mobile_btn_active": "text-indigo-700 bg-indigo-50 border-indigo-200",
    "nav_mobile_btn_inactive": "text-slate-700 hover:text-indigo-700 hover:bg-indigo-50 hover:border-indigo-200",
    "main": "flex-1 w-full relative px-3 pt-4 pb-24 md:pb-8 md:pl-[16.5rem] md:pr-6 md:pt-6 gap-4",
    "topbar": "w-full shrink-0 pt-4 pb-3 md:pt-6 md:pb-4 sticky top-0 z-30 px-3 md:px-0",
    # Single row: menu | search (flex) | actions — wraps only on very narrow screens
    "topbar_inner": (
        "w-full flex flex-row items-center gap-2 sm:gap-3 "
        "rounded-lg border border-slate-200/70 bg-white/95 "
        "shadow-[0_1px_3px_rgba(0,0,0,0.04)] "
        "backdrop-blur-sm py-1.5 px-3 md:px-4"
    ),
    "shell_icon_btn": (
        "min-w-[32px] min-h-[32px] w-8 h-8 flex items-center justify-center "
        "rounded-md border border-slate-200/80 bg-white text-slate-500 "
        "hover:bg-slate-50 hover:text-slate-900 hover:border-slate-300 transition-colors shrink-0"
    ),
    "mobile_menu_btn": (
        "md:hidden min-w-[44px] min-h-[44px] flex items-center justify-center "
        "rounded-md border border-slate-200/80 bg-white text-slate-500 "
        "hover:bg-slate-50 hover:text-slate-900 transition-colors shrink-0"
    ),
    "sidebar_logo": "ff-sidebar-logo w-9 h-9 rounded-none object-contain",
    "header_search": f"{STYLE_INPUT} flex-1 min-w-0 basis-0 sm:max-w-md",
    "menu_wide": "w-[240px] max-w-[calc(100vw-2rem)]",
    "menu": "w-[220px] max-w-[calc(100vw-2rem)]",
    "menu_meta": "text-xs text-slate-600 px-3 pt-2",
    "menu_meta_company": "text-sm text-slate-600 px-3 pb-2",
    "content": "ff-page-enter w-full",
    "user_btn": (
        "min-w-[32px] min-h-[32px] w-8 h-8 flex items-center justify-center "
        "rounded-md border border-indigo-200/60 bg-indigo-50 text-indigo-700 "
        "hover:bg-indigo-100 transition-colors shrink-0 px-1.5"
    ),
    "user_initials": "text-xs font-semibold text-indigo-700",
    "logout_item": "text-rose-600",
}


def layout_wrapper(content_func):
    global _shell_sidebar_ref, _shell_mobile_nav_ref

    identifier = app.storage.user.get("auth_user")
    initials = _avatar_initials(identifier)
    company_name = _active_company_name()
    company_logo_url = "/static/Logo-fixundfertig.svg"
    n8n_today_count = _n8n_documents_today_count()
    is_owner = _is_owner_user()
    # Mobile navigation: use a dialog instead of a Quasar drawer so nothing overlays on desktop.
    mobile_menu = ui.dialog().classes("md:hidden").props("position=left maximized")
    with mobile_menu:
        with ff_card(
            pad="p-4",
            classes="w-full max-w-xs h-full !rounded-none flex flex-col gap-2 !shadow-none",
        ):
            ui.image(company_logo_url).classes("w-12 h-12 object-contain")
            ui.element("div").classes("w-full h-px bg-slate-200")

            @ui.refreshable
            def _shell_mobile_nav() -> None:
                highlight = _sidebar_highlight_target(app.storage.user.get("page", "dashboard"))

                def nav_item_mobile(label: str, target: str, icon: str) -> None:
                    active = highlight == target
                    base = "w-full justify-start gap-3 rounded-xl px-3 py-2 text-left border border-transparent"
                    cls = (
                        f"{base} {_LAYOUT['nav_mobile_btn_active']}"
                        if active
                        else f"{base} {_LAYOUT['nav_mobile_btn_inactive']}"
                    )
                    with ui.button(
                        label,
                        icon=icon,
                        on_click=lambda t=target: (set_page(t), mobile_menu.close()),
                    ).props("flat no-caps").classes(cls):
                        pass

                for item in app_shell_nav_items(is_owner=is_owner):
                    nav_item_mobile(item["label"], item["id"], item["icon"])

            _shell_mobile_nav_ref = _shell_mobile_nav
            _shell_mobile_nav()

    with ui.element("div").classes(_LAYOUT["app_root"]):
        with ui.row().classes(_LAYOUT["shell_row"]):
            # Sidebar
            with ui.column().classes(_LAYOUT["sidebar"]):
                ui.image(company_logo_url).classes(_LAYOUT["sidebar_logo"])

                @ui.refreshable
                def _shell_sidebar_nav() -> None:
                    highlight = _sidebar_highlight_target(app.storage.user.get("page", "dashboard"))

                    def nav_item(label: str, target: str, icon: str) -> None:
                        active = highlight == target
                        cls = (
                            f'{_LAYOUT["nav_btn_base"]} {_LAYOUT["nav_btn_active"]}'
                            if active
                            else f'{_LAYOUT["nav_btn_base"]} {_LAYOUT["nav_btn_inactive"]}'
                        )
                        with ui.button(
                            label,
                            icon=icon,
                            on_click=lambda t=target: set_page(t),
                        ).props("flat no-caps").classes(cls):
                            pass

                    first = True
                    for item in app_shell_nav_items(is_owner=is_owner):
                        # Visuelle Gruppe trennen vor Kunden/Einladungen
                        if first:
                            first = False
                        elif item["id"] in {"customers", "expenses", "invites"}:
                            ui.element("div").classes(_LAYOUT["nav_sep"])
                        nav_item(item["label"], item["id"], item["icon"])

                _shell_sidebar_ref = _shell_sidebar_nav
                _shell_sidebar_nav()

            # Main content
            with ui.column().classes(_LAYOUT["main"]):

                def handle_logout() -> None:
                    clear_auth_session()
                    ui.navigate.to("/login")

                def open_ledger_search(query: str) -> None:
                    app.storage.user["ledger_search_query"] = (query or "").strip()
                    set_page("ledger")

                with ui.column().classes(_LAYOUT["topbar"]):
                    with ui.row().classes(_LAYOUT["topbar_inner"]):
                        ff_icon_button(
                            icon="menu",
                            on_click=mobile_menu.open,
                            classes=_LAYOUT["mobile_menu_btn"],
                            round_button=False,
                        )
                        ui.input(
                            "Search transactions",
                            on_change=lambda e: open_ledger_search(e.value or ""),
                        ).props("outlined dense").classes(_LAYOUT["header_search"])
                        with ui.row().classes("items-center gap-1 sm:gap-2 shrink-0"):
                            with ff_icon_button(icon="notifications", classes=_LAYOUT["shell_icon_btn"]):
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
                                        ui.item("Keine neuen Benachrichtigungen.").classes(
                                            STYLE_TEXT_MUTED
                                        )
                            if not _is_readonly_mode():
                                ff_btn_primary(
                                    "New Invoice",
                                    on_click=lambda: _open_invoice_editor(None),
                                    classes="shrink-0 !py-1.5 !min-h-0 h-9 text-sm",
                                    props="dense",
                                )
                            with ui.button().props("flat dense").classes(_LAYOUT["user_btn"]):
                                ui.label(initials).classes(_LAYOUT["user_initials"])
                                with ui.menu().classes(_LAYOUT["menu"]):
                                    if identifier:
                                        ui.label(identifier).classes(_LAYOUT["menu_meta"])
                                    if company_name:
                                        ui.label(company_name).classes(_LAYOUT["menu_meta_company"])
                                    ui.separator().classes("my-1")
                                    ui.item("Settings", on_click=lambda: go_app_page("settings"))
                                    ui.item("Logout", on_click=handle_logout).classes(
                                        _LAYOUT["logout_item"]
                                    )

                @ui.refreshable
                def _content() -> None:
                    with ui.element("div").classes(_LAYOUT["content"]):
                        content_func()

                global _content_ref
                _content_ref = _content
                _content()

    # Mobile bottom nav bar (position: fixed, hidden on md+)
    _bottom_nav_items = [
        {"id": "dashboard", "label": "Home", "icon": "dashboard"},
        {"id": "invoices", "label": "Rechnungen", "icon": "receipt_long"},
        {"id": "documents", "label": "Belege", "icon": "description"},
        {"id": "ledger", "label": "Finanzen", "icon": "account_balance"},
        {"id": "customers", "label": "Kunden", "icon": "groups"},
    ]
    with ui.element("nav").classes("ff-mobile-bottomnav"):
        for _item in _bottom_nav_items:
            _item_id = _item["id"]
            _item_label = _item["label"]
            _item_icon = _item["icon"]
            _active = _sidebar_highlight_target(app.storage.user.get("page", "dashboard")) == _item_id
            _active_cls = "ff-nav-active" if _active else ""
            with ui.element("div").classes(f"ff-mobile-nav-item {_active_cls}").on(
                "click", lambda t=_item_id: set_page(t)
            ):
                with ui.element("div").classes("ff-nav-dot"):
                    ui.icon(_item_icon).classes("text-[20px]")
                ui.label(_item_label).style("font-size:10px;line-height:1")


# DISABLED: @ui.page("/")
def index():
    apply_global_ui_theme()
    if not require_auth():
        return

    app.add_static_files("/storage", "storage")

    if _is_readonly_mode():
        with ui.row().classes(
            "w-full max-w-7xl mx-auto mb-2 px-4 py-2 rounded bg-amber-100 text-amber-900 text-sm font-semibold items-center gap-2"
        ):
            ui.icon("visibility")
            ui.label("Read-only preview mode")

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

    def content():
        # Read on every render: refreshable content must not close over a stale `page`
        # from the first `index()` call (would break sidebar navigation after set_page).
        page = app.storage.user.get("page", "dashboard")
        if page in {"home", "todos"}:
            page = "dashboard"
            app.storage.user["page"] = page
        if _is_readonly_mode() and page in {"settings", "customer_new", "invoice_create", "invites"}:
            page = "dashboard"
            app.storage.user["page"] = "dashboard"

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
            container_classes = STYLE_CONTAINER
            if page == "dashboard":
                container_classes = f"{STYLE_CONTAINER} px-4 sm:px-6"

            with ui.column().classes(container_classes):
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


# DISABLED: @ui.page("/settings")
def settings_page():
    """Bookmark/deep-link only: shell lives on `/`. Never render a bare page without layout."""
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
        host="0.0.0.0",
        port=8000,
        language="de",
        storage_secret=storage_secret,
        favicon="/static/Logo-fixundfertig.svg",
        reload=False,
    )
