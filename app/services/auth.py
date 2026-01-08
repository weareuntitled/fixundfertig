from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta
from threading import Thread

from sqlmodel import select

from data import Token, TokenPurpose, User, get_session, get_valid_token
from services.email import send_email

VERIFY_TOKEN_TTL = timedelta(hours=24)
RESET_TOKEN_TTL = timedelta(hours=2)
logger = logging.getLogger(__name__)


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


def _mask_token(token: str | None, visible: int = 4) -> str:
    if not token:
        return ""
    token_str = str(token)
    if len(token_str) <= visible * 2:
        return "***"
    return f"{token_str[:visible]}...{token_str[-visible:]}"


def _send_welcome_email(email_normalized: str) -> None:
    try:
        send_email(
            email_normalized,
            "Welcome!",
            "Welcome to Fix & Fertig! Your account has been created.",
        )
        logger.info(
            "create_user_pending.welcome_email_sent",
            extra={"email": email_normalized},
        )
    except Exception as exc:
        logger.error(
            "create_user_pending.welcome_email_failed",
            exc_info=exc,
            extra={"email": email_normalized},
        )


def _dispatch_welcome_email(email_normalized: str) -> None:
    if os.getenv("SEND_WELCOME_EMAIL") != "1":
        return
    Thread(
        target=_send_welcome_email,
        args=(email_normalized,),
        daemon=True,
    ).start()
    logger.info(
        "create_user_pending.welcome_email_queued",
        extra={"email": email_normalized},
    )


def create_user_pending(email: str, username: str, password: str) -> tuple[User, str]:
    email_normalized = (email or "").strip().lower()
    username_clean = (username or "").strip() or None
    if not email_normalized:
        logger.warning(
            "create_user_pending.invalid_email",
            extra={"email": email_normalized, "username": username_clean},
        )
        raise ValueError("Email is required")
    if not password:
        logger.warning(
            "create_user_pending.missing_password",
            extra={"email": email_normalized, "username": username_clean},
        )
        raise ValueError("Password is required")

    logger.info(
        "create_user_pending.start",
        extra={"email": email_normalized, "username": username_clean},
    )
    with get_session() as session:
        existing = session.exec(select(User).where(User.email == email_normalized)).first()
        if existing:
            logger.warning(
                "create_user_pending.email_exists",
                extra={"email": email_normalized, "username": username_clean},
            )
            raise ValueError("User already exists")
        if username_clean:
            existing_username = session.exec(
                select(User).where(User.username == username_clean)
            ).first()
            if existing_username:
                logger.warning(
                    "create_user_pending.username_exists",
                    extra={"email": email_normalized, "username": username_clean},
                )
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

    masked_token = _mask_token(token_str)
    try:
        send_email(
            email_normalized,
            "Verify your email",
            f"Use this token to verify your email: {token_str}",
        )
        logger.info(
            "create_user_pending.verify_email_sent",
            extra={"email": email_normalized, "token": masked_token},
        )
    except Exception as exc:
        logger.error(
            "create_user_pending.verify_email_failed",
            exc_info=exc,
            extra={"email": email_normalized, "token": masked_token},
        )

    _dispatch_welcome_email(email_normalized)

    logger.info(
        "create_user_pending.success",
        extra={"email": email_normalized, "token": masked_token},
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
        if not user.is_email_verified and _email_verification_required():
            return False
        if not user.is_email_verified:
            user.is_email_verified = True
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
            token_str = token.token
            email_value = user.email
            session.commit()
            send_email(
                email_value,
                "Reset your password",
                f"Use this token to reset your password: {token_str}",
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
