import logging
from datetime import datetime, timedelta, date
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Appointment, Consultation
from app.services.notifications import send_email

logger=logging.getLogger(__name__)
scheduler=BackgroundScheduler()

def reminder_job():
    db=SessionLocal()
    try:
        now=datetime.now(); upper=now+timedelta(hours=24)
        rows=db.scalars(select(Appointment).where(Appointment.reminder_sent.is_(False),Appointment.status=="Booked",Appointment.appointment_date>=now.date(),Appointment.appointment_date<=upper.date())).all()
        for a in rows:
            slot=datetime.combine(a.appointment_date,a.slot_time)
            if now < slot <= upper:
                send_email(a.patient.email,"Appointment reminder",f"Reminder: appointment {a.appointment_number} with Dr. {a.doctor.name} at {slot}.")
                a.reminder_sent=True
        db.commit()
    except Exception: logger.exception("Reminder job failed")
    finally: db.close()

def no_show_job():
    db=SessionLocal()
    try:
        cutoff=datetime.now()-timedelta(minutes=30)
        rows=db.scalars(select(Appointment).where(Appointment.status=="Booked",Appointment.appointment_date<=cutoff.date())).all()
        for a in rows:
            if datetime.combine(a.appointment_date,a.slot_time)<cutoff:
                a.status="No-Show"
        db.commit()
    except Exception: logger.exception("No-show job failed")
    finally: db.close()

def followup_job():
    db=SessionLocal()
    try:
        tomorrow=date.today()+timedelta(days=1)
        rows=db.scalars(select(Consultation).where(Consultation.follow_up_date==tomorrow)).all()
        for c in rows:
            send_email(c.appointment.patient.email,"Follow-up reminder",f"Your follow-up date is {tomorrow}.")
    except Exception: logger.exception("Follow-up job failed")
    finally: db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(reminder_job,"interval",hours=1,id="appointment_reminders",replace_existing=True)
        scheduler.add_job(no_show_job,"interval",minutes=15,id="no_show",replace_existing=True)
        scheduler.add_job(followup_job,"cron",hour=8,id="followup",replace_existing=True)
        scheduler.start()

def stop_scheduler():
    if scheduler.running: scheduler.shutdown(wait=False)
