from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta

from sqlmodel import select

from data import Token, TokenPurpose, User, get_session, get_valid_token
from services.email import send_email

VERIFY_TOKEN_TTL = timedelta(hours=24)
RESET_TOKEN_TTL = timedelta(hours=2)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _get_user_by_identifier(session, identifier: str | None) -> User | None:
    lookup = (identifier or "").strip().lower()
    if not lookup:
        return None
    statement = select(User).where(User.email == lookup)
    user = session.exec(statement).first()
    if user:
        return user
    statement = select(User).where(User.username == lookup)
    return session.exec(statement).first()


def _create_token(user: User, purpose: TokenPurpose, expires_in: timedelta) -> Token:
    token = Token(
        user_id=user.id,
        token=uuid.uuid4().hex,
        purpose=purpose,
        expires_at=datetime.utcnow() + expires_in,
    )
    return token


def create_user_pending(email: str, username: str, password: str) -> tuple[int, str, str]:
    email_normalized = (email or "").strip().lower()
    username_clean = (username or "").strip() or None
    if not email_normalized:
        raise ValueError("Email is required")
    if not password:
        raise ValueError("Password is required")

    with get_session() as session:
        existing = session.exec(select(User).where(User.email == email_normalized)).first()
        if existing:
            raise ValueError("User already exists")
        if username_clean:
            existing_username = session.exec(
                select(User).where(User.username == username_clean)
            ).first()
            if existing_username:
                raise ValueError("Username already exists")

        user = User(
            email=email_normalized,
            username=username_clean,
            password_hash=_hash_password(password),
            is_active=False,
            is_email_verified=False,
        )
        session.add(user)
        session.flush()

        token = _create_token(user, TokenPurpose.VERIFY_EMAIL, VERIFY_TOKEN_TTL)
        session.add(token)
        user_id = user.id
        email_value = user.email
        token_str = token.token
        session.commit()

    send_email(
        email_value,
        "Verify your email",
        f"Use this token to verify your email: {token_str}",
    )
    return user_id, email_value, token_str


def create_verify_email_token(user_id: int) -> str:
    with get_session() as session:
        user = session.exec(select(User).where(User.id == user_id)).first()
        if not user:
            raise ValueError("User not found")
        token = _create_token(user, TokenPurpose.VERIFY_EMAIL, VERIFY_TOKEN_TTL)
        session.add(token)
        email_value = user.email
        token_str = token.token
        session.commit()

    send_email(
        email_value,
        "Verify your email",
        f"Use this token to verify your email: {token_str}",
    )
    return token_str


def verify_email(token_str: str) -> bool:
    with get_session() as session:
        token = get_valid_token(session, token_str, TokenPurpose.VERIFY_EMAIL)
        if not token:
            return False
        user = session.exec(select(User).where(User.id == token.user_id)).first()
        if not user:
            return False
        user.is_email_verified = True
        token.used_at = datetime.utcnow()
        session.add(user)
        session.add(token)
        session.commit()
        return True


def verify_password(identifier: str, password: str) -> bool:
    with get_session() as session:
        user = _get_user_by_identifier(session, identifier)
        if not user:
            return False
        return user.password_hash == _hash_password(password or "")


def login_user(identifier: str) -> bool:
    with get_session() as session:
        user = _get_user_by_identifier(session, identifier)
        if not user:
            return False
        if not user.is_email_verified:
            return False
        user.is_active = True
        session.add(user)
        session.commit()
        return True


def request_password_reset(identifier: str) -> bool:
    with get_session() as session:
        user = _get_user_by_identifier(session, identifier)
        if user:
            token = _create_token(user, TokenPurpose.RESET_PASSWORD, RESET_TOKEN_TTL)
            session.add(token)
            session.commit()
            send_email(
                user.email,
                "Reset your password",
                f"Use this token to reset your password: {token.token}",
            )
    return True


def reset_password(token_str: str, new_password: str) -> bool:
    if not new_password:
        return False
    with get_session() as session:
        token = get_valid_token(session, token_str, TokenPurpose.RESET_PASSWORD)
        if not token:
            return False
        user = session.exec(select(User).where(User.id == token.user_id)).first()
        if not user:
            return False
        user.password_hash = _hash_password(new_password)
        token.used_at = datetime.utcnow()
        session.add(user)
        session.add(token)
        session.commit()
        return True
