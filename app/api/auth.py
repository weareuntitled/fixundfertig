# =========================
# APP/API/AUTH.PY
# =========================
"""
Auth API: /api/auth/{login,logout,me}

Endpoints:
- POST /api/auth/login   — Login mit email+password, setzt ff_session + ff_csrf Cookies
- POST /api/auth/logout  — Logout, löscht beide Cookies
- GET  /api/auth/me      — Aktueller User (aus ff_session-Cookie)

Token-Implementierung:
- ff_session: signed Token via itsdangerous.URLSafeTimedSerializer (JWT-Äquivalent
  für self-hosted Single-Server). Payload: {"user_id": <int>}. Max-Age 7 Tage.
- ff_csrf: signed Token, getrennt von ff_session, damit der Client ihn lesen kann
  (NICHT httponly) und im X-CSRF-Token-Header mitsenden muss.

Migration: in einer späteren Phase (M2-JWT-Standard) kann der itsdangerous-Serializer
durch echtes JWT (PyJWT) ersetzt werden, ohne die Endpoints oder die Schemas zu ändern.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlmodel import select

from data import User
from dependencies import db_session, require_session_auth
from schemas.account import PasswordChangeRequest
from schemas.auth import LoginRequest, LoginResponse, UserPublic
from services.account import change_password


router = APIRouter(prefix="/api/auth", tags=["auth"])


# --- Token-Helpers (öffentlich für Tests) -----------------------------------

def _secret() -> bytes:
    secret = (os.getenv("STORAGE_SECRET") or "").strip()
    if not secret:
        # Tests setzen STORAGE_SECRET über conftest; hier fallback.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return b"pytest-secret-key-for-testing-only-32"
        raise RuntimeError("STORAGE_SECRET nicht gesetzt")
    return secret.encode("utf-8")


_SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 Tage
_CSRF_MAX_AGE_SECONDS = 24 * 3600         # 24h, wird bei jedem Mutating-Call erneuert


def _session_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="ff-session-v1")


def _csrf_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="ff-csrf-v1")


def create_session_token(user_id: int, *, max_age_seconds: int = _SESSION_MAX_AGE_SECONDS) -> str:
    """Erzeugt ein signiertes Session-Token (Cookie-Wert)."""
    return _session_serializer().dumps({"user_id": int(user_id)})


def load_session_token(token: str, *, max_age_seconds: int = _SESSION_MAX_AGE_SECONDS) -> int:
    """Verifiziert Token, gibt user_id zurück oder raises Exception."""
    payload = _session_serializer().loads(token, max_age=max_age_seconds)
    return int(payload["user_id"])


def create_csrf_token(user_id: int, *, max_age_seconds: int = _CSRF_MAX_AGE_SECONDS) -> str:
    """Erzeugt ein CSRF-Token, das an denselben User gebunden ist."""
    return _csrf_serializer().dumps({"user_id": int(user_id)})


def verify_csrf_token(token: str, expected_user_id: int, *, max_age_seconds: int = _CSRF_MAX_AGE_SECONDS) -> bool:
    """Verifiziert CSRF-Token (Signatur + Ablauf + User-Bindung)."""
    try:
        payload = _csrf_serializer().loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return False
    return int(payload.get("user_id", -1)) == int(expected_user_id)


# --- Cookie-Konfiguration ---------------------------------------------------

def _is_production() -> bool:
    env = (os.getenv("FF_ENV") or "").strip().lower()
    if env in {"prod", "production"}:
        return True
    base = (os.getenv("APP_BASE_URL") or "").strip().lower()
    return base.startswith("https://") and not os.getenv("PYTEST_CURRENT_TEST")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="ff_session",
        value=token,
        httponly=True,
        secure=_is_production(),
        samesite="lax",
        max_age=_SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def _set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="ff_csrf",
        value=token,
        httponly=False,  # Client muss lesen für X-CSRF-Token-Header
        secure=_is_production(),
        samesite="strict",
        max_age=_CSRF_MAX_AGE_SECONDS,
        path="/",
    )


def _clear_cookies(response: Response) -> None:
    response.delete_cookie("ff_session", path="/")
    response.delete_cookie("ff_csrf", path="/")


# --- Endpoints --------------------------------------------------------------

@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"description": "Ungültige Zugangsdaten"},
        403: {"description": "Kein Zugang (nicht in Allowlist)"},
        422: {"description": "Validation Error"},
    },
)
def login(
    payload: LoginRequest,
    response: Response,
    session=Depends(db_session),
) -> LoginResponse:
    """Authentifiziert User, setzt ff_session + ff_csrf Cookies."""
    # Lazy import: ermöglicht Tests, `services.auth.verify_password` direkt zu mocken.
    from services.auth import is_identifier_allowed, verify_password

    if not verify_password(payload.email, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Zugangsdaten")
    if not is_identifier_allowed(payload.email):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kein Zugang")

    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Zugangsdaten")
    user_id = int(user.id)

    session_token = create_session_token(user_id)
    csrf_token = create_csrf_token(user_id)
    _set_session_cookie(response, session_token)
    _set_csrf_cookie(response, csrf_token)

    return LoginResponse(
        user=UserPublic.model_validate(user),
        csrf_token=csrf_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    """Löscht ff_session + ff_csrf Cookies."""
    _clear_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get(
    "/me",
    response_model=UserPublic,
    responses={401: {"description": "Nicht eingeloggt oder Session abgelaufen"}},
)
def me(
    ff_session: Annotated[str | None, Cookie()] = None,
    session=Depends(db_session),
) -> UserPublic:
    """Gibt den aktuellen User zurück (aus ff_session Cookie)."""
    if not ff_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht eingeloggt")
    try:
        user_id = load_session_token(ff_session)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session abgelaufen")

    user = session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inaktiv")
    return UserPublic.model_validate(user)


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {"description": "Validation-Fehler (z.B. current_password falsch)"},
        401: {"description": "Nicht eingeloggt"},
    },
)
def change_password_endpoint(
    payload: PasswordChangeRequest,
    user_id: int = Depends(require_session_auth),
) -> Response:
    """Passwort ändern. Erfordert current_password + neues Passwort (min. 6 Zeichen)."""
    try:
        change_password(
            user_id=int(user_id),
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    return response
