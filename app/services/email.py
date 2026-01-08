# app/services/email.py
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger(__name__)


def _load_env_smtp_config() -> dict[str, Any] | None:
    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("SMTP_FROM") or user

    missing = [
        name
        for name, value in {
            "SMTP_HOST": host,
            "SMTP_PORT": port,
            "SMTP_USER": user,
            "SMTP_PASS": password,
        }.items()
        if not value
    ]
    if missing:
        return None

    try:
        port_value = int(port)
    except ValueError as exc:
        raise ValueError(f"Invalid SMTP_PORT value: {port}") from exc

    return {
        "host": host,
        "port": port_value,
        "user": user,
        "password": password,
        "sender": sender,
    }


def _normalize_config(cfg: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cfg:
        return None
    host = (cfg.get("host") or "").strip()
    user = (cfg.get("user") or "").strip()
    password = (cfg.get("password") or "").strip()
    sender = (cfg.get("sender") or "").strip() or user
    port = cfg.get("port")

    if not host or not user or not password or not port:
        return None

    try:
        port = int(port)
    except Exception:
        return None

    return {"host": host, "port": port, "user": user, "password": password, "sender": sender}


def send_email(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    smtp_config: dict[str, Any] | None = None,
) -> bool:
    """
    smtp_config optional:
      { "host": str, "port": int, "user": str, "password": str, "sender": str(optional) }
    If not provided, env SMTP_* is used.
    Port 465 uses SMTP_SSL. Other ports use SMTP + STARTTLS.
    """
    cfg = _normalize_config(smtp_config) or _load_env_smtp_config()
    if not cfg:
        logger.warning("SMTP config missing. Skipping email to=%s subject=%s", to, subject)
        return False

    to = (to or "").strip()
    subject = (subject or "").strip()
    if not to:
        raise ValueError("Recipient address is required")
    if not subject:
        raise ValueError("Email subject is required")
    if not text:
        raise ValueError("Email text content is required")

    msg = EmailMessage()
    msg["From"] = cfg["sender"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    host = cfg["host"]
    port = int(cfg["port"])
    user = cfg["user"]
    password = cfg["password"]

    logger.info("smtp.send to=%s host=%s port=%s", to, host, port)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=12) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(user, password)
                smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("smtp.failed to=%s subject=%s", to, subject)
        raise RuntimeError("Failed to send email via SMTP") from exc

    return True
