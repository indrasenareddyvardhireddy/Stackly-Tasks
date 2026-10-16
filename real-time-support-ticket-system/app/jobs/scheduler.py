from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.jobs.auto_close_job import auto_close_resolved_tickets
from app.jobs.escalation_job import run_escalations
from app.jobs.sla_job import check_sla_breaches

scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler() -> None:
    # SLA check first; escalation runs 30s later in the same 5-minute cycle so it sees fresh breaches
    scheduler.add_job(check_sla_breaches, IntervalTrigger(minutes=5), id="sla_check",
                      max_instances=1, coalesce=True, replace_existing=True)
    scheduler.add_job(
        run_escalations,
        IntervalTrigger(minutes=5, start_date=datetime.now(timezone.utc) + timedelta(seconds=30)),
        id="escalation", max_instances=1, coalesce=True, replace_existing=True,
    )
    scheduler.add_job(auto_close_resolved_tickets, CronTrigger(hour=2, minute=0), id="auto_close",
                      max_instances=1, coalesce=True, replace_existing=True)
    scheduler.start()


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
