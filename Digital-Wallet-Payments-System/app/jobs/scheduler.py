import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.jobs import tasks

logger = logging.getLogger("wallet.scheduler")
scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler():
    if scheduler.running:
        return
    scheduler.add_job(tasks.cashback_job, "interval", hours=1, id="cashback", max_instances=1, coalesce=True)
    scheduler.add_job(tasks.withdrawal_job, "interval", minutes=5, id="withdrawals", max_instances=1, coalesce=True)
    scheduler.add_job(tasks.request_expiry_job, "interval", hours=1, id="request_expiry", max_instances=1, coalesce=True)
    scheduler.add_job(tasks.cleanup_job, "cron", hour=2, minute=0, id="cleanup", max_instances=1)
    scheduler.add_job(tasks.reconciliation_job, "cron", hour=2, minute=30, id="reconciliation", max_instances=1)
    scheduler.start()
    logger.info("Scheduler started with %s jobs", len(scheduler.get_jobs()))


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
