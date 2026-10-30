"""
Emails are sent through BackgroundTasks (or a daemon thread when there is no request),
so API responses are never delayed. A failing email is logged and never breaks the main action.
All functions receive plain dicts / strings - never ORM objects - because the DB session
is closed by the time a background task runs.
"""
import logging
import mimetypes
import os
import smtplib
import threading
from email.message import EmailMessage
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def dispatch(background_tasks, fn, *args, **kwargs):
    """Run `fn` in FastAPI BackgroundTasks when available, otherwise in a daemon thread."""
    if background_tasks is not None:
        background_tasks.add_task(fn, *args, **kwargs)
    else:
        threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True).start()


def send_email(to: str, subject: str, body: str, attachment_path: Optional[str] = None) -> bool:
    try:
        if not settings.SMTP_HOST:
            logger.info("[EMAIL - SMTP not configured] to=%s subject=%s\n%s", to, subject, body)
            return True
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        if attachment_path and os.path.exists(attachment_path):
            ctype = mimetypes.guess_type(attachment_path)[0] or "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)
            with open(attachment_path, "rb") as f:
                msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                                   filename=os.path.basename(attachment_path))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s (subject: %s)", to, subject)
        return False


def _show_block(ctx: dict) -> str:
    return (f"Booking : {ctx['booking_number']}\n"
            f"Event   : {ctx['event_title']}\n"
            f"Venue   : {ctx['venue_name']} - {ctx['screen_name']}\n"
            f"Show    : {ctx['show_datetime']}\n"
            f"Seats   : {ctx['seats']}\n")


def send_booking_confirmed(ctx: dict, pdf_path: Optional[str]):
    body = (f"Hi {ctx['customer_name']},\n\nYour booking is confirmed! Your ticket is attached.\n\n"
            f"{_show_block(ctx)}Amount paid: Rs. {ctx['amount']}\n\n"
            "Show the QR code on the ticket at the entry gate.\n")
    send_email(ctx["customer_email"], f"Booking confirmed - {ctx['booking_number']}", body, pdf_path)


def send_payment_failed(ctx: dict):
    body = (f"Hi {ctx['customer_name']},\n\nYour payment of Rs. {ctx['amount']} failed.\n\n"
            f"{_show_block(ctx)}\nYou can retry the payment until your seat lock expires.\n")
    send_email(ctx["customer_email"], f"Payment failed - {ctx['booking_number']}", body)


def send_late_payment_refund(ctx: dict, reason: Optional[str] = None):
    reason = reason or ("Your payment was received after your seat lock expired and the seats were taken by "
                        "someone else.")
    body = (f"Hi {ctx['customer_name']},\n\n{reason} Rs. {ctx['amount']} has been refunded automatically.\n\n"
            f"{_show_block(ctx)}")
    send_email(ctx["customer_email"], f"Payment refunded - {ctx['booking_number']}", body)


def send_booking_cancelled(ctx: dict, refund_amount: str):
    body = (f"Hi {ctx['customer_name']},\n\nYour booking has been cancelled.\n\n{_show_block(ctx)}\n"
            f"Refund amount: Rs. {refund_amount}\n")
    send_email(ctx["customer_email"], f"Booking cancelled - {ctx['booking_number']}", body)


def send_show_cancelled(ctx: dict, refund_amount: str):
    body = (f"Hi {ctx['customer_name']},\n\nUnfortunately the organizer has cancelled this show.\n\n"
            f"{_show_block(ctx)}\nA full refund of Rs. {refund_amount} (including convenience fee and GST) "
            "has been issued.\n")
    send_email(ctx["customer_email"], f"Show cancelled - {ctx['event_title']}", body)


def send_waitlist_available(to: str, name: str, event_title: str, show_datetime: str, seats: int, category: Optional[str]):
    cat = f" in {category}" if category else ""
    body = (f"Hi {name},\n\nGood news! {seats} seat(s){cat} are now available for {event_title} "
            f"({show_datetime}). Seats are first come, first served - book now!\n")
    send_email(to, f"Seats available - {event_title}", body)


def send_show_reminder(ctx: dict):
    body = (f"Hi {ctx['customer_name']},\n\nReminder: your show starts soon.\n\n{_show_block(ctx)}\n"
            "Please carry your ticket QR code.\n")
    send_email(ctx["customer_email"], f"Reminder: {ctx['event_title']} starts soon", body)
