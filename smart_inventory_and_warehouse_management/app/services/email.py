import logging, smtplib
from email.message import EmailMessage
from app.config import settings
logger=logging.getLogger(__name__)

def send_email(to:str,subject:str,body:str):
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD: logger.warning("SMTP not configured"); return
    try:
        msg=EmailMessage(); msg["From"]=settings.SMTP_FROM or settings.SMTP_USERNAME; msg["To"]=to; msg["Subject"]=subject; msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST,settings.SMTP_PORT,timeout=15) as s:
            s.starttls(); s.login(settings.SMTP_USERNAME,settings.SMTP_PASSWORD); s.send_message(msg)
    except Exception: logger.exception("Email delivery failed")
