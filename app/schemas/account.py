"""Schema für /api/auth/password."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)
