import logging
import os
import smtplib
from email.message import EmailMessage


logger = logging.getLogger(__name__)


def _load_smtp_config() -> dict:
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
        raise ValueError(f"Missing SMTP configuration: {', '.join(missing)}")
    try:
        port_value = int(port)
    except ValueError as exc:
        raise ValueError(f"Invalid SMTP_PORT value: {port}") from exc
    if port_value <= 0:
        raise ValueError(f"Invalid SMTP_PORT value: {port_value}")
    return {
        "host": host,
        "port": port_value,
        "user": user,
        "password": password,
        "sender": sender,
    }


def send_email(to, subject, text, html=None) -> bool:
    config = _load_smtp_config()

    if not to:
        raise ValueError("Recipient address is required")
    if not subject:
        raise ValueError("Email subject is required")
    if not text:
        raise ValueError("Email text content is required")

    message = EmailMessage()
    message["From"] = config["sender"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    logger.info("Sending email to=%s subject=%s", to, subject)

    try:
        with smtplib.SMTP_SSL(
            config["host"],
            config["port"],
            timeout=10,
        ) as smtp:
            smtp.login(config["user"], config["password"])
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("Failed to send email to=%s subject=%s", to, subject)
        raise RuntimeError("Failed to send email via SMTP") from exc
    return True
