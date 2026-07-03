from email.message import EmailMessage
import smtplib

from app.config import get_settings


def smtp_enabled() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


def send_email(to_email: str, subject: str, body: str) -> bool:
    settings = get_settings()
    if not smtp_enabled():
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    smtp_factory = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
    with smtp_factory(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_tls and settings.smtp_port != 465:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)
    return True
