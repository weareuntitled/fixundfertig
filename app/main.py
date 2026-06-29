# =========================
# APP/MAIN.PY
# =========================

import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from starlette.responses import RedirectResponse
from nicegui import ui, app, helpers
from nicegui.storage import Storage, PseudoPersistentDict, request_contextvar
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from env import load_env

load_env()

from logging_setup import setup_logging

setup_logging()

from auth_guard import set_request_for_context
from services.auth import ensure_owner_user

logger = logging.getLogger(__name__)

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

    if (os.getenv("FF_ALLOW_LOCALHOST") or "").strip() == "1":
        hosts.extend(["localhost", "127.0.0.1"])

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
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            request = Request(scope, receive, send)
            set_request_for_context(request)
        await self.app(scope, receive, send)


_configure_security_middleware()
app.add_middleware(_RequestContextMiddleware)

from api import api_router
app.include_router(api_router)


from starlette.staticfiles import StaticFiles as _StaticFiles
from starlette.responses import FileResponse as _FileResponse

_REACT_DIST = Path(__file__).resolve().parent / "static" / "frontend"
_REACT_INDEX = _REACT_DIST / "index.html"


class _ReactSPA(_StaticFiles):
    def __init__(self):
        directory = str(_REACT_DIST) if _REACT_DIST.is_dir() else str(Path(__file__).resolve().parent)
        super().__init__(directory=directory, html=True)

    async def get_response(self, path, scope):
        if not path or path == "" or ("." not in path.split("/")[-1]):
            if _REACT_INDEX.is_file():
                return _FileResponse(str(_REACT_INDEX))
        return await super().get_response(path, scope)


if _REACT_DIST.is_dir():
    app.mount("/static/frontend", _StaticFiles(directory=str(_REACT_DIST), html=True), name="react-static")
    app.mount("/", _ReactSPA(), name="react-spa-root")


app.add_static_files("/static", str(Path(__file__).resolve().parent / "static"))
_FAVICON_PATH = Path(__file__).resolve().parent / "static" / "Logo-fixundfertig.svg"


@app.get("/favicon.ico")
def favicon_ico():
    if not _FAVICON_PATH.is_file():
        raise HTTPException(status_code=404, detail="favicon not found")
    return RedirectResponse(url="/static/Logo-fixundfertig.svg", status_code=307)


if not _IS_PYTEST:
    try:
        ensure_owner_user()
    except Exception:
        logger.exception("Failed to ensure owner user")


if _IS_PYTEST:
    _dummy_request = type("DummyRequest", (), {"session": {"id": "pytest"}})()
    request_contextvar.set(_dummy_request)
    if "pytest" not in app.storage._users:
        app.storage._users["pytest"] = PseudoPersistentDict()
        app.storage._users["pytest"].initialize_sync()

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
