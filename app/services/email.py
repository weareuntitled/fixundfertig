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
    missing = [name for name, value in {
        "SMTP_HOST": host,
        "SMTP_PORT": port,
        "SMTP_USER": user,
        "SMTP_PASS": password,
    }.items() if not value]
    if missing:
        raise ValueError(f"Missing SMTP configuration: {', '.join(missing)}")
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


def send_email(to, subject, text, html=None) -> bool:
    config = _load_smtp_config()

    message = EmailMessage()
    message["From"] = config["sender"]
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    logger.info("Sending email to=%s subject=%s", to, subject)

    if config["port"] == 465:
        with smtplib.SMTP_SSL(config["host"], config["port"]) as smtp:
            smtp.login(config["user"], config["password"])
            smtp.send_message(message)
    else:
        with smtplib.SMTP(config["host"], config["port"]) as smtp:
            smtp.starttls()
            smtp.login(config["user"], config["password"])
            smtp.send_message(message)
    return True
