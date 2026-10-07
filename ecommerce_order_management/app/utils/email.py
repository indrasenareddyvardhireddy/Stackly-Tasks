import logging
import smtplib
from email.message import EmailMessage
from app.database import settings

logger = logging.getLogger(__name__)

def send_email(to_email: str, subject: str, body: str):
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.warning("SMTP credentials are not configured; email skipped.")
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
        msg["To"] = to_email
        msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        logger.exception("Email sending failed for %s", to_email)
