import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.models.booking import Booking
from app.models.enums import BookingStatus, EventStatus, ShowStatus
from app.models.event import Event, Show
from app.services import cache_service, email_service
from app.services.booking_service import booking_context
from app.utils.time import now

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def expire_bookings_job():
    """Every minute: Pending Payment bookings past expires_at -> Expired."""
    db = SessionLocal()
    try:
        n = (db.query(Booking).filter(Booking.status == BookingStatus.PENDING.value, Booking.expires_at < now())
             .update({"status": BookingStatus.EXPIRED.value, "updated_at": now()}, synchronize_session=False))
        db.commit()
        if n:
            logger.info("Expired %s pending bookings", n)
    except Exception:
        db.rollback()
        logger.exception("expire_bookings_job failed")
    finally:
        db.close()


def reminder_job():
    """Every 30 min: email customers whose show starts within 3 hours (once per booking)."""
    db = SessionLocal()
    try:
        t = now()
        bookings = (db.query(Booking).join(Show, Show.id == Booking.show_id)
                    .filter(Booking.status == BookingStatus.CONFIRMED.value, Booking.reminder_sent.is_(False),
                            Show.status == ShowStatus.SCHEDULED.value,
                            Show.start_at > t, Show.start_at <= t + timedelta(hours=3)).all())
        for b in bookings:
            ctx = booking_context(b)
            b.reminder_sent = True
            db.commit()                                 # mark first so a crash can never double-send
            email_service.send_show_reminder(ctx)
    except Exception:
        db.rollback()
        logger.exception("reminder_job failed")
    finally:
        db.close()


def complete_shows_job():
    """Every 15 min: Scheduled shows whose end_time has passed -> Completed."""
    db = SessionLocal()
    try:
        n = (db.query(Show).filter(Show.status == ShowStatus.SCHEDULED.value, Show.end_at < now())
             .update({"status": ShowStatus.COMPLETED.value, "updated_at": now()}, synchronize_session=False))
        db.commit()
        if n:
            logger.info("Completed %s shows", n)
            cache_service.clear_event_cache()
    except Exception:
        db.rollback()
        logger.exception("complete_shows_job failed")
    finally:
        db.close()


def complete_events_job():
    """Daily: Published events whose shows are ALL Completed -> Completed."""
    db = SessionLocal()
    try:
        changed = 0
        for event in db.query(Event).filter(Event.status == EventStatus.PUBLISHED.value).all():
            statuses = {s.status for s in event.shows if s.status != ShowStatus.CANCELLED.value}
            if statuses and statuses == {ShowStatus.COMPLETED.value}:
                event.status = EventStatus.COMPLETED.value
                changed += 1
        db.commit()
        if changed:
            logger.info("Completed %s events", changed)
            cache_service.clear_event_cache()
    except Exception:
        db.rollback()
        logger.exception("complete_events_job failed")
    finally:
        db.close()


def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(expire_bookings_job, "interval", minutes=1, id="expire_bookings", replace_existing=True)
    scheduler.add_job(reminder_job, "interval", minutes=30, id="reminders", replace_existing=True)
    scheduler.add_job(complete_shows_job, "interval", minutes=15, id="complete_shows", replace_existing=True)
    scheduler.add_job(complete_events_job, CronTrigger(hour=0, minute=10), id="complete_events", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
