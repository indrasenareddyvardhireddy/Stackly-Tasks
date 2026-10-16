from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentProfile, Ticket, User, agent_categories
from app.models.enums import OPEN_STATUSES, Availability, Role, TicketStatus
from app.services.history import add_history
from app.services.notification_service import notify, push_open_counts


async def open_ticket_counts(db: AsyncSession, agent_ids: List[int]) -> Dict[int, int]:
    if not agent_ids:
        return {}
    rows = await db.execute(
        select(Ticket.assigned_agent_id, func.count(Ticket.id))
        .where(Ticket.assigned_agent_id.in_(agent_ids), Ticket.status.in_(OPEN_STATUSES))
        .group_by(Ticket.assigned_agent_id)
    )
    return {r[0]: r[1] for r in rows.all()}


async def find_best_agent(db: AsyncSession, category_id: int) -> Optional[User]:
    """Online + active agent handling the category, with the fewest open tickets and spare capacity."""
    stmt = (
        select(User)
        .join(AgentProfile, AgentProfile.user_id == User.id)
        .join(agent_categories, agent_categories.c.agent_id == AgentProfile.user_id)
        .where(
            User.role == Role.AGENT,
            User.is_active.is_(True),
            AgentProfile.availability == Availability.ONLINE,
            agent_categories.c.category_id == category_id,
        )
    )
    agents = (await db.execute(stmt)).scalars().all()
    if not agents:
        return None
    counts = await open_ticket_counts(db, [a.id for a in agents])
    eligible = [a for a in agents if counts.get(a.id, 0) < a.agent_profile.max_open_tickets]
    if not eligible:
        return None
    return min(eligible, key=lambda a: (counts.get(a.id, 0), a.id))


async def assign_to_agent(db: AsyncSession, ticket: Ticket, agent: User) -> None:
    ticket.assigned_agent_id = agent.id
    if ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.ASSIGNED
        await add_history(
            db, ticket.id, "status_change", TicketStatus.OPEN, TicketStatus.ASSIGNED, None,
            f"Automatically assigned to {agent.name}",
        )
    await db.flush()
    await notify(
        db, agent.id, "ticket_assigned", "New ticket assigned",
        f"Ticket {ticket.ticket_number} has been assigned to you.", ticket.id,
    )
    await push_open_counts(db, [agent.id])


async def auto_assign(db: AsyncSession, ticket: Ticket) -> bool:
    agent = await find_best_agent(db, ticket.category_id)
    if agent is None:
        return False
    await assign_to_agent(db, ticket, agent)
    return True


async def assign_pending_tickets(db: AsyncSession) -> int:
    """Assign unassigned Open tickets (most urgent / oldest first) to any matching available agent."""
    res = await db.execute(
        select(Ticket)
        .where(Ticket.status == TicketStatus.OPEN, Ticket.assigned_agent_id.is_(None))
        .order_by(Ticket.priority.desc(), Ticket.created_at.asc())
        .limit(200)
    )
    assigned = 0
    for ticket in res.scalars().all():
        if await auto_assign(db, ticket):
            assigned += 1
    return assigned
