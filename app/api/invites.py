# =========================
# APP/API/INVITES.PY
# =========================
"""
Invites API: /api/invites[/...]

Endpoints:
- GET    /api/invites         — Liste der Allowlist
- POST   /api/invites         — E-Mail hinzufügen
- DELETE /api/invites/{email} — E-Mail entfernen

Backing: Tabelle `invitedemail` (siehe `app/data.py:InvitedEmail`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from data import InvitedEmail, get_session
from dependencies import db_session, require_session_auth
from schemas.invite import InviteCreate, InviteRead


router = APIRouter(prefix="/api/invites", tags=["invites"])


@router.get("", response_model=list[InviteRead])
def list_invites(
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """List all invited emails (allowlist for registration)."""
    invites = session.exec(select(InvitedEmail)).all()
    return [
        InviteRead(
            email=getattr(inv, "email", ""),
            invited_at=str(getattr(inv, "invited_at", "") or ""),
        )
        for inv in invites
    ]


@router.post("", response_model=InviteRead, status_code=status.HTTP_201_CREATED)
def add_invite(
    payload: InviteCreate,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Add an email to the allowlist."""
    existing = session.exec(
        select(InvitedEmail).where(InvitedEmail.email == payload.email)
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-Mail ist bereits in der Allowlist",
        )
    new_invite = InvitedEmail(email=payload.email, invited_at=datetime.now().isoformat())
    session.add(new_invite)
    session.commit()
    session.refresh(new_invite)
    return InviteRead(
        email=new_invite.email,
        invited_at=str(new_invite.invited_at or ""),
    )


@router.delete("/{email}")
def remove_invite(
    email: str,
    _user_id: int = Depends(require_session_auth),
    session: Iterator = Depends(db_session),
):
    """Remove an email from the allowlist."""
    existing = session.exec(
        select(InvitedEmail).where(InvitedEmail.email == email)
    ).first()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="E-Mail nicht in Allowlist"
        )
    session.delete(existing)
    session.commit()
    return {"status": "deleted"}
