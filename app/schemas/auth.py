# =========================
# APP/SCHEMAS/AUTH.PY
# =========================
"""
Pydantic v2 Schemas für Auth.

Source of Truth für `/api/auth/*`-Endpoints.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LoginRequest(BaseModel):
    """Input für POST /api/auth/login."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        if not _EMAIL_PATTERN.match(v):
            raise ValueError("Ungültiges E-Mail-Format")
        return v.lower()


class UserPublic(BaseModel):
    """Output für GET /api/auth/me — minimal sichere User-Darstellung."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str = ""
    last_name: str = ""
    is_active: bool = True
    email_verified: bool = False


class LoginResponse(BaseModel):
    """Output für POST /api/auth/login."""

    user: UserPublic
    csrf_token: str


__all__ = ["LoginRequest", "LoginResponse", "UserPublic"]
