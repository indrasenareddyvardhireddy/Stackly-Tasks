import logging
from datetime import timedelta

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Ticket
from app.models.enums import TicketStatus
from app.services.ticket_service import apply_status
from app.utils import utcnow

logger = logging.getLogger(__name__)


async def auto_close_resolved_tickets() -> None:
    """Daily: close Resolved tickets the customer hasn't reopened within 7 days."""
    try:
        async with AsyncSessionLocal() as db:
            cutoff = utcnow() - timedelta(days=7)
            tickets = (
                await db.execute(
                    select(Ticket).where(Ticket.status == TicketStatus.RESOLVED, Ticket.resolved_at <= cutoff)
                )
            ).scalars().all()
            for t in tickets:
                await apply_status(db, t, TicketStatus.CLOSED, None, "Auto-closed: not reopened within 7 days of resolution")
            await db.commit()
            logger.info("Auto-close job closed %d ticket(s)", len(tickets))
    except Exception:
        logger.exception("Auto-close job failed")
