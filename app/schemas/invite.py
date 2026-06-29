# =========================
# APP/SCHEMAS/INVITE.PY
# =========================
"""
Pydantic v2 Schemas für Invite.

Source of Truth für `/api/invites/*`-Endpoints.
"""

from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field

from .auth import _EMAIL_PATTERN


class InviteCreate(BaseModel):
    """Input für POST /api/invites."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=200)

    @classmethod
    def __get_validators__(cls):  # pragma: no cover (legacy)
        yield from super().__get_validators__()

    @classmethod
    def _validate_email(cls, v: str) -> str:  # type: ignore[no-redef]
        if not _EMAIL_PATTERN.match(v):
            raise ValueError("Ungültiges E-Mail-Format")
        return v.lower()

    from pydantic import field_validator
    _validate = field_validator("email")(_validate_email)


class InviteRead(BaseModel):
    """Output für GET /api/invites und POST /api/invites (response)."""

    model_config = ConfigDict(from_attributes=True)

    email: str
    invited_at: str = ""


__all__ = ["InviteCreate", "InviteRead"]
