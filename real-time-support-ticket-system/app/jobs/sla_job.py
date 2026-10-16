import asyncio
import logging

from sqlalchemy import and_, or_, select

from app.database import AsyncSessionLocal
from app.models import Ticket, User
from app.models.enums import ACTIVE_STATUSES, Role, TicketStatus
from app.services.email_service import send_email
from app.services.notification_service import notify_admins
from app.utils import utcnow

logger = logging.getLogger(__name__)


async def check_sla_breaches() -> None:
    """Every 5 minutes: flag tickets whose first-response or resolution deadline has passed.

    The resolution timer is paused while a ticket is 'Waiting on Customer'.
    """
    try:
        async with AsyncSessionLocal() as db:
            now = utcnow()
            stmt = select(Ticket).where(
                Ticket.status.in_(ACTIVE_STATUSES),
                or_(
                    and_(
                        Ticket.first_response_at.is_(None),
                        Ticket.first_response_breached.is_(False),
                        Ticket.first_response_due < now,
                    ),
                    and_(
                        Ticket.status != TicketStatus.WAITING,
                        Ticket.resolution_breached.is_(False),
                        Ticket.resolution_due < now,
                    ),
                ),
            )
            tickets = (await db.execute(stmt)).scalars().all()
            if not tickets:
                return
            admin_emails = [
                r[0] for r in (await db.execute(select(User.email).where(User.role == Role.ADMIN, User.is_active.is_(True)))).all()
            ]
            for t in tickets:
                reasons = []
                if t.first_response_at is None and not t.first_response_breached and t.first_response_due < now:
                    t.first_response_breached = True
                    reasons.append("first response")
                if t.status != TicketStatus.WAITING and not t.resolution_breached and t.resolution_due < now:
                    t.resolution_breached = True
                    reasons.append("resolution")
                if not reasons:
                    continue
                t.sla_breached = True
                text = f"Ticket {t.ticket_number} breached its {' and '.join(reasons)} SLA."
                await notify_admins(db, "sla_breached", "SLA breached", text, t.id)
                for email in admin_emails:
                    await asyncio.to_thread(send_email, email, f"[{t.ticket_number}] SLA breached", text)
            await db.commit()
            logger.info("SLA check flagged %d ticket(s)", len(tickets))
    except Exception:
        logger.exception("SLA check job failed")
