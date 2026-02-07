import contextvars
import logging
import os

from nicegui import app, ui

from services.auth import ensure_local_test_user, is_identifier_allowed

logger = logging.getLogger(__name__)

# Current request for localhost detection (set by middleware in main.py).
_request_cv: contextvars.ContextVar = contextvars.ContextVar("ff_request", default=None)


def set_request_for_context(request) -> None:
    """Set the current request so FF_NO_LOGIN_LOCAL can check the Host header. Called from main middleware."""
    _request_cv.set(request)


def _is_localhost_request() -> bool:
    """True if the current request Host is localhost or 127.0.0.1."""
    req = _request_cv.get(None)
    if req is None:
        return False
    headers = getattr(req, "headers", None)
    if not headers:
        return False
    raw = headers.get("host") if hasattr(headers, "get") else getattr(req, "scope", {}).get("headers", {}).get(b"host", b"")
    if raw is None:
        return False
    if isinstance(raw, bytes):
        raw = raw.decode("latin1")
    hostname = (raw.split(":")[0] or "").strip().lower()
    return hostname in ("localhost", "127.0.0.1")


def _auth_disabled() -> bool:
    # Never disable auth automatically in test runs (CI/dev machines might have FF_DISABLE_AUTH set).
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    # No-login when accessing from localhost and flag set (works even with FF_ENV=production).
    if os.getenv("FF_NO_LOGIN_LOCAL") == "1" and _is_localhost_request():
        return True
    disabled = os.getenv("FF_DISABLE_AUTH") == "1"
    if disabled and (os.getenv("FF_ENV") or "").strip().lower() in {"prod", "production"}:
        raise RuntimeError("FF_DISABLE_AUTH must not be enabled in production")
    return disabled


def _local_test_username() -> str:
    return (os.getenv("FF_LOCAL_TEST_USER") or "djdanep").strip() or "djdanep"


def _local_test_password() -> str:
    password = os.getenv("FF_LOCAL_TEST_PASSWORD")
    if password:
        return password
    raise RuntimeError("FF_LOCAL_TEST_PASSWORD must be set when FF_DISABLE_AUTH=1 or FF_NO_LOGIN_LOCAL=1")


def _local_test_email(username: str) -> str:
    return (os.getenv("FF_LOCAL_TEST_EMAIL") or f"{username}@local").strip() or f"{username}@local"


def _ensure_local_auth_session() -> str:
    username = _local_test_username()
    password = _local_test_password()
    email = _local_test_email(username)
    try:
        ensure_local_test_user(email=email, username=username, password=password)
    except Exception:
        logger.exception("Failed to ensure local test user")
    app.storage.user["auth_user"] = username
    return username


def is_authenticated(*, redirect: bool = False) -> bool:
    if _auth_disabled():
        _ensure_local_auth_session()
        return True

    identifier = app.storage.user.get("auth_user")
    if identifier and is_identifier_allowed(identifier):
        return True
    if identifier:
        app.storage.user.pop("auth_user", None)
    if redirect:
        ui.navigate.to("/login")
    return False


def require_auth() -> bool:
    return is_authenticated(redirect=True)


def clear_auth_session() -> None:
    app.storage.user.pop("auth_user", None)
