import os
import smtplib
from email.message import EmailMessage


def _load_smtp_config():
    host = os.getenv('SMTP_HOST')
    port = os.getenv('SMTP_PORT')
    user = os.getenv('SMTP_USER')
    password = os.getenv('SMTP_PASSWORD')
    sender = os.getenv('SMTP_FROM')
    missing = [name for name, value in {
        'SMTP_HOST': host,
        'SMTP_PORT': port,
        'SMTP_USER': user,
        'SMTP_PASSWORD': password,
        'SMTP_FROM': sender,
    }.items() if not value]
    if missing:
        return None, f"Missing SMTP configuration: {', '.join(missing)}"
    try:
        port_value = int(port)
    except ValueError:
        return None, f'Invalid SMTP_PORT value: {port}'
    return {
        'host': host,
        'port': port_value,
        'user': user,
        'password': password,
        'sender': sender,
    }, None


def send_email(to, subject, body):
    config, error = _load_smtp_config()
    if error:
        print(
            f'Email not sent ({error}). '
            f'To="{to}", Subject="{subject}", Body="{body}"'
        )
        return

    message = EmailMessage()
    message['From'] = config['sender']
    message['To'] = to
    message['Subject'] = subject
    message.set_content(body)

    with smtplib.SMTP(config['host'], config['port']) as smtp:
        smtp.starttls()
        smtp.login(config['user'], config['password'])
        smtp.send_message(message)
