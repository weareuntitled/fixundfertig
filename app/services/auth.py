from __future__ import annotations

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import secrets
from typing import Optional
from passlib.context import CryptContext

from sqlmodel import Field, Session, SQLModel, select

from data import engine

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    username: str
    password_hash: str
    is_active: bool = False
    is_email_verified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Token(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token: str = Field(index=True, unique=True)
    purpose: str = Field(index=True)
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


SQLModel.metadata.create_all(engine)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return "pbkdf2_sha256$200000${}${}".format(
        base64.urlsafe_b64encode(salt).decode("utf-8"),
        base64.urlsafe_b64encode(hashed).decode("utf-8"),
    )


def _create_token(session: Session, user: User, purpose: str, ttl: timedelta) -> Token:
    token = Token(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        purpose=purpose,
        expires_at=_utcnow() + ttl,
    )
    session.add(token)
    session.commit()
    session.refresh(token)
    return token


def send_email(to_email: str, subject: str, body: str) -> None:
    print("Sending email to", to_email)
    print("Subject:", subject)
    print(body)


def create_user_pending(email: str, username: str, password: str) -> User:
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        raise ValueError("Email is required")

    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == normalized_email)).first()
        if existing:
            raise ValueError("Email already in use")

        user = User(
            email=normalized_email,
            username=username,
            password_hash=_hash_password(password),
            is_active=False,
            is_email_verified=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def create_verify_email_token(user: User) -> Token:
    if not user.id:
        raise ValueError("User must be persisted")
    with Session(engine) as session:
        persisted = session.get(User, user.id)
        if not persisted:
            raise ValueError("User not found")
        return _create_token(session, persisted, "verify_email", timedelta(hours=24))


def _get_valid_token(session: Session, token_str: str, purpose: str) -> Token | None:
    token = session.exec(
        select(Token).where(Token.token == token_str, Token.purpose == purpose)
    ).first()
    if not token:
        return None
    now = _utcnow()
    if token.used_at is not None:
        return None
    if token.expires_at <= now:
        return None
    return token


def verify_email(token_str: str) -> None:
    with Session(engine) as session:
        token = _get_valid_token(session, token_str, "verify_email")
        if not token:
            raise ValueError("Invalid or expired token")
        user = session.get(User, token.user_id)
        if not user:
            raise ValueError("User not found")

        user.is_email_verified = True
        user.is_active = True
        token.used_at = _utcnow()

        session.add(user)
        session.add(token)
        session.commit()


def request_password_reset(email: str) -> Token | None:
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == normalized_email)).first()
        if not user:
            return None
        token = _create_token(session, user, "reset_password", timedelta(hours=1))

    reset_link = f"https://example.com/reset-password?token={token.token}"
    send_email(
        to_email=normalized_email,
        subject="Password reset",
        body=f"Use this link to reset your password: {reset_link}",
    )
    return token


def reset_password(token_str: str, new_password: str) -> None:
    with Session(engine) as session:
        token = _get_valid_token(session, token_str, "reset_password")
        if not token:
            raise ValueError("Invalid or expired token")
        user = session.get(User, token.user_id)
        if not user:
            raise ValueError("User not found")

        user.password_hash = _hash_password(new_password)
        token.used_at = _utcnow()

        session.add(user)
        session.add(token)
        session.commit()





def _ensure_min_length(plain: str) -> None:
    if len(plain) < 10:
        raise ValueError("Password must be at least 10 characters long.")



def verify_password(plain: str, hash: str) -> bool:
    _ensure_min_length(plain)
    return _pwd_context.verify(plain, hash)
