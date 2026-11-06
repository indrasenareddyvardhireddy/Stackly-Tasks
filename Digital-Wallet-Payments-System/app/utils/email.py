"""Email helpers. Emails are always sent in the background; failures are only logged."""
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("wallet.email")


def send_email(to: str, subject: str, body: str) -> None:
    try:
        if not settings.SMTP_HOST:
            logger.info("[EMAIL not sent - SMTP not configured] to=%s subject=%s body=%s", to, subject, body)
            return
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception:  # never break a money action because of an email problem
        logger.exception("Failed to send email to %s (%s)", to, subject)


class Notifier:
    """Collects emails during a request and sends them only after the DB commit succeeds."""

    def __init__(self):
        self.items = []

    def add(self, to: str, subject: str, body: str):
        if to:
            self.items.append((to, subject, body))

    def flush(self, background_tasks=None):
        for to, subject, body in self.items:
            if background_tasks is not None:
                background_tasks.add_task(send_email, to, subject, body)
            else:
                send_email(to, subject, body)
        self.items = []
