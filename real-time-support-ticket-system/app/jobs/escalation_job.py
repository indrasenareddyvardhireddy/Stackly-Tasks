import logging

from sqlalchemy import and_, or_, select

from app.database import AsyncSessionLocal
from app.models import Ticket
from app.models.enums import ACTIVE_STATUSES, Priority
from app.services.history import add_history
from app.services.notification_service import notify_admins

logger = logging.getLogger(__name__)

NEXT_PRIORITY = {Priority.LOW: Priority.MEDIUM, Priority.MEDIUM: Priority.HIGH, Priority.HIGH: Priority.URGENT}


async def run_escalations() -> None:
    """Escalate each SLA breach exactly once: raise priority by one level, notify admins, log history.

    Urgent tickets cannot go higher but admins are still notified.
    """
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(Ticket).where(
                Ticket.status.in_(ACTIVE_STATUSES),
                or_(
                    and_(Ticket.first_response_breached.is_(True), Ticket.first_response_escalated.is_(False)),
                    and_(Ticket.resolution_breached.is_(True), Ticket.resolution_escalated.is_(False)),
                ),
            )
            tickets = (await db.execute(stmt)).scalars().all()
            for t in tickets:
                pending = []
                if t.first_response_breached and not t.first_response_escalated:
                    t.first_response_escalated = True
                    pending.append("first response")
                if t.resolution_breached and not t.resolution_escalated:
                    t.resolution_escalated = True
                    pending.append("resolution")
                for reason in pending:
                    old = t.priority
                    new = NEXT_PRIORITY.get(old)
                    if new is not None:
                        t.priority = new
                        note = f"Escalated after {reason} SLA breach: priority {old.value} -> {new.value}"
                        msg = f"Ticket {t.ticket_number} was escalated ({old.value} -> {new.value}) after a {reason} SLA breach."
                    else:
                        note = f"{reason.capitalize()} SLA breached; ticket is already Urgent and cannot be escalated further"
                        msg = f"Ticket {t.ticket_number} breached its {reason} SLA and is already Urgent."
                    await add_history(db, t.id, "escalation", t.status, t.status, None, note)
                    await notify_admins(db, "ticket_escalated", "Ticket escalated", msg, t.id)
            await db.commit()
            if tickets:
                logger.info("Escalation job processed %d ticket(s)", len(tickets))
    except Exception:
        logger.exception("Escalation job failed")
