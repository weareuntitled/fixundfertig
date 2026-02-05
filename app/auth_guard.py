import logging
import os

from nicegui import app, ui

from services.auth import ensure_local_test_user, is_identifier_allowed

logger = logging.getLogger(__name__)


def _auth_disabled() -> bool:
    return os.getenv("FF_DISABLE_AUTH") == "1"


def _local_test_username() -> str:
    return (os.getenv("FF_LOCAL_TEST_USER") or "djdanep").strip() or "djdanep"


def _local_test_password() -> str:
    return os.getenv("FF_LOCAL_TEST_PASSWORD") or "123456"


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
