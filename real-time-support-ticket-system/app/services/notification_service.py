from typing import Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, Ticket, User
from app.models.enums import OPEN_STATUSES, Role, TicketStatus
from app.schemas.notification import NotificationOut
from app.websockets.manager import notification_manager


async def notify(
    db: AsyncSession,
    user_id: int,
    ntype: str,
    title: str,
    message: str,
    ticket_id: Optional[int] = None,
) -> Notification:
    """Persist a notification and push it live if the user is connected."""
    n = Notification(user_id=user_id, type=ntype, title=title, message=message, ticket_id=ticket_id, is_read=False)
    db.add(n)
    await db.flush()
    await notification_manager.send(
        user_id, {"type": "notification", "data": NotificationOut.model_validate(n).model_dump(mode="json")}
    )
    return n


async def admin_ids(db: AsyncSession) -> List[int]:
    rows = await db.execute(select(User.id).where(User.role == Role.ADMIN, User.is_active.is_(True)))
    return [r[0] for r in rows.all()]


async def notify_admins(db: AsyncSession, ntype: str, title: str, message: str, ticket_id: Optional[int] = None) -> None:
    for aid in await admin_ids(db):
        await notify(db, aid, ntype, title, message, ticket_id)


async def agent_open_count(db: AsyncSession, agent_id: int) -> int:
    res = await db.execute(
        select(func.count(Ticket.id)).where(Ticket.assigned_agent_id == agent_id, Ticket.status.in_(OPEN_STATUSES))
    )
    return res.scalar_one()


async def global_open_count(db: AsyncSession) -> int:
    res = await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED])
        )
    )
    return res.scalar_one()


async def open_count_for(db: AsyncSession, user_id: int, role: Role) -> Optional[int]:
    if role == Role.AGENT:
        return await agent_open_count(db, user_id)
    if role == Role.ADMIN:
        return await global_open_count(db)
    return None


async def push_open_counts(db: AsyncSession, agent_ids: Iterable[int]) -> None:
    """Live open-ticket counters for the given agents and for all admins."""
    for aid in set(agent_ids):
        await notification_manager.send(
            aid, {"type": "open_tickets_count", "count": await agent_open_count(db, aid)}
        )
    total = await global_open_count(db)
    for admin_id in await admin_ids(db):
        await notification_manager.send(admin_id, {"type": "open_tickets_count", "count": total})
