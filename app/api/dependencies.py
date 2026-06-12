# =========================
# APP/API/DEPENDENCIES.PY
# =========================
"""
FastAPI-Dependencies für Auth, User-Lookup, Company-Lookup.

Session-basiert via das `ff_session`-Cookie (vom React-Frontend gesetzt).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Annotated, Iterator, Optional

from fastapi import Cookie, Depends, HTTPException, status

from auth_guard import is_authenticated
from data import Company, User, get_session
from pages._shared import get_current_user_id, get_primary_company


@contextmanager
def get_session_dep() -> Iterator[object]:
    """Context-Manager-Wrapper um `get_session` — bleibt für Code, der `with` braucht."""
    with get_session() as session:
        yield session


def db_session() -> Iterator[object]:
    """FastAPI-Dependency: yields eine aktive DB-Session."""
    with get_session() as session:
        yield session


def _user_id_from_ff_session(ff_session: Optional[str]) -> Optional[int]:
    """Validate the API's `ff_session` cookie and return the user_id, or None."""
    if not ff_session:
        return None
    try:
        from api.auth import load_session_token
        return load_session_token(ff_session)
    except Exception:
        return None


def require_session_auth(
    ff_session: Annotated[Optional[str], Cookie(alias="ff_session")] = None,
) -> int:
    """Returns the current user_id, raises 401 if not authenticated.

    Liest das `ff_session`-Cookie direkt via FastAPI's Cookie()-Injection.
    Fallback auf `is_authenticated()` (Starlette Session) für NiceGUI-Routen.
    """
    user_id = _user_id_from_ff_session(ff_session)
    if user_id is not None:
        return int(user_id)
    if is_authenticated():
        with get_session() as session:
            return get_current_user_id(session)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required")


def get_current_user(user_id: int = Depends(require_session_auth)) -> User:
    """Loads the full User record for the authenticated session."""
    with get_session() as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user


def get_current_company(user_id: int = Depends(require_session_auth)) -> Company:
    """Loads the primary Company of the authenticated user."""
    with get_session() as session:
        comp = get_primary_company(session, user_id)
        if not comp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No company for user")
        return comp


__all__ = [
    "require_session_auth",
    "get_current_user",
    "get_current_company",
    "get_session_dep",
    "db_session",
]
