from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta
from threading import Thread

from sqlmodel import select

from data import InvitedEmail, Token, TokenPurpose, User, get_session, get_valid_token
from services.email import send_email

VERIFY_TOKEN_TTL = timedelta(hours=24)
RESET_TOKEN_TTL = timedelta(hours=2)
logger = logging.getLogger(__name__)
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "").strip().lower()
OWNER_PASSWORD = os.getenv("OWNER_PASSWORD", "")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _owner_email() -> str:
    return OWNER_EMAIL


def _owner_password() -> str:
    return OWNER_PASSWORD


def ensure_owner_user() -> None:
    owner_email = _owner_email()
    owner_password = _owner_password()
    if not owner_email or not owner_password:
        return
    with get_session() as session:
        user = session.exec(select(User).where(User.email == owner_email)).first()
        if user:
            if user.password_hash != _hash_password(owner_password):
                user.password_hash = _hash_password(owner_password)
                user.is_active = True
                user.is_email_verified = True
                session.add(user)
                session.commit()
            return
        user = User(
            email=owner_email,
            username="admin",
            password_hash=_hash_password(owner_password),
            is_active=True,
            is_email_verified=True,
        )
        session.add(user)
        session.commit()


def _is_email_allowed_in_session(session, email: str | None) -> bool:
    email_normalized = _normalize_email(email)
    if not email_normalized:
        return False
    if email_normalized == _owner_email():
        return True
    return session.exec(select(InvitedEmail).where(InvitedEmail.email == email_normalized)).first() is not None


def is_email_allowed(email: str | None) -> bool:
    with get_session() as session:
        return _is_email_allowed_in_session(session, email)


def is_identifier_allowed(identifier: str | None) -> bool:
    with get_session() as session:
        user = _get_user_by_identifier(session, identifier or "")
        if not user:
            return False
        return _is_email_allowed_in_session(session, user.email)


def _email_verification_required() -> bool:
    explicit_setting = os.getenv("REQUIRE_EMAIL_VERIFICATION")
    if explicit_setting is not None:
        return explicit_setting == "1"
    return all(
        os.getenv(name)
        for name in (
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASS",
        )
    )


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


def _app_base_url() -> str:
    return os.getenv("APP_BASE_URL", "http://localhost:8080").rstrip("/")


def _build_verify_link(token: str) -> str:
    return f"{_app_base_url()}/verify?token={token}"


def _build_reset_link(token: str) -> str:
    return f"{_app_base_url()}/reset?token={token}"


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


def create_user_pending(email: str, username: str, password: str) -> tuple[int, str, str | None]:
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
    if not is_email_allowed(email_normalized):
        logger.warning(
            "create_user_pending.not_allowed",
            extra={"email": email_normalized, "username": username_clean},
        )
        raise ValueError("Nur mit Einladung möglich")

    logger.info(
        "create_user_pending.start",
        extra={"email": email_normalized, "username": username_clean},
    )
    verification_required = _email_verification_required()
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
            is_email_verified=not verification_required,
        )
        session.add(user)
        session.flush()

        user_id = user.id
        email_value = user.email
        token_str = None
        if verification_required:
            token = _create_token(user, TokenPurpose.VERIFY_EMAIL, VERIFY_TOKEN_TTL)
            session.add(token)
            token_str = token.token
        session.commit()

    masked_token = _mask_token(token_str)
    if verification_required and token_str:
        verify_link = _build_verify_link(token_str)
        try:
            send_email(
                email_normalized,
                "Verify your email",
                (
                    "Verify your email using this link:\n"
                    f"{verify_link}\n\n"
                    f"If the link does not work, use this token: {token_str}"
                ),
                (
                    "<p>Verify your email using this link:</p>"
                    f"<p><a href=\"{verify_link}\">{verify_link}</a></p>"
                    f"<p>If the link does not work, use this token: <code>{token_str}</code></p>"
                ),
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

    verify_link = _build_verify_link(token_str)
    send_email(
        email_value,
        "Verify your email",
        (
            "Verify your email using this link:\n"
            f"{verify_link}\n\n"
            f"If the link does not work, use this token: {token_str}"
        ),
        (
            "<p>Verify your email using this link:</p>"
            f"<p><a href=\"{verify_link}\">{verify_link}</a></p>"
            f"<p>If the link does not work, use this token: <code>{token_str}</code></p>"
        ),
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
        if not _is_email_allowed_in_session(session, user.email):
            logger.warning(
                "login_user.not_allowed",
                extra={"email": user.email},
            )
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
            reset_link = _build_reset_link(token_str)
            send_email(
                email_value,
                "Reset your password",
                (
                    "Reset your password using this link:\n"
                    f"{reset_link}\n\n"
                    f"If the link does not work, use this token: {token_str}"
                ),
                (
                    "<p>Reset your password using this link:</p>"
                    f"<p><a href=\"{reset_link}\">{reset_link}</a></p>"
                    f"<p>If the link does not work, use this token: <code>{token_str}</code></p>"
                ),
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


def list_invited_emails() -> list[InvitedEmail]:
    with get_session() as session:
        statement = select(InvitedEmail).order_by(InvitedEmail.invited_at.desc())
        return list(session.exec(statement))


def add_invited_email(email: str, invited_by_user_id: int | None = None) -> InvitedEmail:
    email_normalized = _normalize_email(email)
    if not email_normalized or "@" not in email_normalized:
        raise ValueError("Ungültige E-Mail-Adresse")
    if email_normalized == _owner_email():
        raise ValueError("Owner hat bereits Zugriff")
    with get_session() as session:
        existing = session.exec(select(InvitedEmail).where(InvitedEmail.email == email_normalized)).first()
        if existing:
            return existing
        invited = InvitedEmail(email=email_normalized, invited_by_user_id=invited_by_user_id)
        session.add(invited)
        session.commit()
        session.refresh(invited)
        return invited


def remove_invited_email(email: str) -> bool:
    email_normalized = _normalize_email(email)
    if not email_normalized:
        return False
    if email_normalized == _owner_email():
        return False
    with get_session() as session:
        existing = session.exec(select(InvitedEmail).where(InvitedEmail.email == email_normalized)).first()
        if not existing:
            return False
        session.delete(existing)
        session.commit()
        return True
