from datetime import timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Ticket, User
from app.models.enums import OPEN_STATUSES, Priority, Role, TicketStatus
from app.schemas.ticket import TicketCreate
from app.services.assignment_service import assign_pending_tickets, auto_assign, open_ticket_counts
from app.services.history import add_history
from app.services.notification_service import notify, push_open_counts
from app.services.sla_service import compute_due_times, get_policy
from app.utils import utcnow

# Allowed status flow: Open -> Assigned -> In Progress -> (Waiting on Customer | Resolved) -> Closed
TRANSITIONS = {
    TicketStatus.OPEN: [TicketStatus.ASSIGNED],
    TicketStatus.ASSIGNED: [TicketStatus.IN_PROGRESS],
    TicketStatus.IN_PROGRESS: [TicketStatus.WAITING, TicketStatus.RESOLVED],
    TicketStatus.WAITING: [TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED],
    TicketStatus.RESOLVED: [TicketStatus.CLOSED],
    TicketStatus.CLOSED: [],
}
REOPEN_WINDOW = timedelta(days=7)
MAX_REOPENS = 2


# ---------- access helpers ----------
def can_access_ticket(user: User, ticket: Ticket) -> bool:
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.AGENT:
        return ticket.assigned_agent_id == user.id
    return ticket.customer_id == user.id


def can_manage_ticket(user: User, ticket: Ticket) -> bool:
    """Only the assigned agent or an admin can change status / priority."""
    return user.role == Role.ADMIN or (user.role == Role.AGENT and ticket.assigned_agent_id == user.id)


async def get_ticket_or_404(db: AsyncSession, ticket_id: int) -> Ticket:
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


async def get_accessible_ticket(db: AsyncSession, ticket_id: int, user: User) -> Ticket:
    ticket = await get_ticket_or_404(db, ticket_id)
    if not can_access_ticket(user, ticket):
        raise HTTPException(status_code=403, detail="You do not have access to this ticket")
    return ticket


# ---------- creation ----------
async def _next_ticket_number(db: AsyncSession, now) -> str:
    prefix = f"TKT-{now.strftime('%Y%m%d')}-"
    res = await db.execute(select(func.max(Ticket.ticket_number)).where(Ticket.ticket_number.like(prefix + "%")))
    last = res.scalar_one_or_none()
    seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


async def create_ticket(db: AsyncSession, customer: User, data: TicketCreate) -> Ticket:
    category = await db.get(Category, data.category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if not category.is_active:
        raise HTTPException(status_code=400, detail="This category is inactive and cannot be used for new tickets")

    now = utcnow()
    policy = await get_policy(db, data.priority)
    fr_due, res_due = compute_due_times(now, policy)

    ticket = None
    for _ in range(5):  # retry on the (rare) ticket-number race
        number = await _next_ticket_number(db, now)
        ticket = Ticket(
            ticket_number=number, customer_id=customer.id, category_id=category.id,
            subject=data.subject, description=data.description, priority=data.priority,
            status=TicketStatus.OPEN, first_response_due=fr_due, resolution_due=res_due,
            created_at=now,
        )
        try:
            async with db.begin_nested():
                db.add(ticket)
            break
        except IntegrityError:
            ticket = None
    if ticket is None:
        raise HTTPException(status_code=500, detail="Could not generate a unique ticket number, please retry")

    await add_history(db, ticket.id, "status_change", None, TicketStatus.OPEN, customer.id, "Ticket created")
    await auto_assign(db, ticket)  # stays Open + unassigned if nobody is available
    await push_open_counts(db, [])
    return ticket


# ---------- status ----------
async def apply_status(
    db: AsyncSession,
    ticket: Ticket,
    new_status: TicketStatus,
    changed_by: Optional[int],
    note: Optional[str] = None,
    notify_customer: bool = True,
) -> None:
    """Apply a status change (no flow validation) with SLA pause bookkeeping, history and notifications."""
    old = ticket.status
    now = utcnow()

    # Leaving "Waiting on Customer": shift the resolution deadline by the time spent waiting
    if old == TicketStatus.WAITING and new_status != TicketStatus.WAITING and ticket.waiting_since:
        delta = int((now - ticket.waiting_since).total_seconds())
        ticket.paused_seconds += delta
        ticket.resolution_due = ticket.resolution_due + timedelta(seconds=delta)
        ticket.waiting_since = None
    if new_status == TicketStatus.WAITING:
        ticket.waiting_since = now

    if new_status == TicketStatus.RESOLVED:
        ticket.resolved_at = now
        if now > ticket.resolution_due and not ticket.resolution_breached:
            # resolved late but before the SLA job noticed: count it as a breach, nothing to escalate
            ticket.resolution_breached = True
            ticket.resolution_escalated = True
            ticket.sla_breached = True
    if new_status == TicketStatus.CLOSED:
        ticket.closed_at = now

    ticket.status = new_status
    await add_history(db, ticket.id, "status_change", old, new_status, changed_by, note)
    await db.flush()

    if notify_customer:
        await notify(
            db, ticket.customer_id, "ticket_status_changed", f"Ticket {ticket.ticket_number} updated",
            f"Status changed from {old.value} to {new_status.value}.", ticket.id,
        )
    await push_open_counts(db, [ticket.assigned_agent_id] if ticket.assigned_agent_id else [])

    if new_status == TicketStatus.RESOLVED:
        await assign_pending_tickets(db)  # an agent just freed capacity


async def change_status(db: AsyncSession, ticket: Ticket, new_status: TicketStatus, user: User, note: Optional[str] = None):
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Closed tickets cannot be updated")
    if new_status not in TRANSITIONS[ticket.status]:
        allowed = ", ".join(s.value for s in TRANSITIONS[ticket.status]) or "none"
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition: {ticket.status.value} -> {new_status.value}. Allowed: {allowed}",
        )
    if new_status == TicketStatus.ASSIGNED and ticket.assigned_agent_id is None:
        raise HTTPException(status_code=400, detail="Assign an agent to the ticket first")
    await apply_status(db, ticket, new_status, user.id, note)
    return ticket


async def record_first_response(db: AsyncSession, ticket: Ticket) -> None:
    now = utcnow()
    ticket.first_response_at = now
    if now > ticket.first_response_due and not ticket.first_response_breached:
        ticket.first_response_breached = True
        ticket.first_response_escalated = True  # already late: nothing left to escalate
        ticket.sla_breached = True


# ---------- priority ----------
async def change_priority(db: AsyncSession, ticket: Ticket, new_priority: Priority, user: User) -> Ticket:
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Closed tickets cannot be updated")
    if new_priority == ticket.priority:
        raise HTTPException(status_code=400, detail="Ticket already has this priority")
    old = ticket.priority
    policy = await get_policy(db, new_priority)
    fr_due, res_due = compute_due_times(ticket.created_at, policy, ticket.paused_seconds)
    if ticket.first_response_at is None:
        ticket.first_response_due = fr_due
    ticket.resolution_due = res_due
    ticket.priority = new_priority
    await add_history(
        db, ticket.id, "priority_change", ticket.status, ticket.status, user.id,
        f"Priority changed from {old.value} to {new_priority.value}; SLA due times recalculated",
    )
    await db.flush()
    return ticket


# ---------- reopen ----------
async def reopen_ticket(db: AsyncSession, ticket: Ticket, user: User) -> Ticket:
    if ticket.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Only the ticket's customer can reopen it")
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Closed tickets cannot be reopened")
    if ticket.status != TicketStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="Only Resolved tickets can be reopened")
    if ticket.reopen_count >= MAX_REOPENS:
        raise HTTPException(status_code=400, detail=f"A ticket can be reopened at most {MAX_REOPENS} times")
    now = utcnow()
    if ticket.resolved_at is None or now - ticket.resolved_at > REOPEN_WINDOW:
        raise HTTPException(status_code=400, detail="Tickets can only be reopened within 7 days of resolution")

    # time spent Resolved does not count toward the resolution SLA
    delta = int((now - ticket.resolved_at).total_seconds())
    ticket.paused_seconds += delta
    ticket.resolution_due = ticket.resolution_due + timedelta(seconds=delta)
    ticket.reopen_count += 1
    ticket.resolved_at = None
    await apply_status(db, ticket, TicketStatus.IN_PROGRESS, user.id, "Reopened by customer", notify_customer=False)
    if ticket.assigned_agent_id:
        await notify(
            db, ticket.assigned_agent_id, "ticket_reopened", f"Ticket {ticket.ticket_number} reopened",
            "The customer reopened this ticket.", ticket.id,
        )
    return ticket


# ---------- manual (re)assignment ----------
async def reassign_ticket(db: AsyncSession, ticket: Ticket, agent_id: int, admin: User) -> Ticket:
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=400, detail="Closed tickets cannot be reassigned")
    agent = await db.get(User, agent_id)
    if agent is None or agent.role != Role.AGENT or agent.agent_profile is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent.is_active:
        raise HTTPException(status_code=400, detail="Agent is inactive")
    if ticket.assigned_agent_id == agent.id:
        raise HTTPException(status_code=400, detail="Ticket is already assigned to this agent")
    if ticket.status != TicketStatus.RESOLVED:
        counts = await open_ticket_counts(db, [agent.id])
        if counts.get(agent.id, 0) >= agent.agent_profile.max_open_tickets:
            raise HTTPException(status_code=400, detail="Agent has reached max_open_tickets")

    old_agent_id = ticket.assigned_agent_id
    old_status = ticket.status
    ticket.assigned_agent_id = agent.id
    if ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.ASSIGNED
    old_label = f"agent #{old_agent_id}" if old_agent_id else "unassigned"
    await add_history(
        db, ticket.id, "assignment", old_status, ticket.status, admin.id,
        f"Reassigned from {old_label} to {agent.name} (agent #{agent.id}) by admin",
    )
    await db.flush()
    await notify(db, agent.id, "ticket_assigned", "Ticket assigned to you",
                 f"Ticket {ticket.ticket_number} was assigned to you by an admin.", ticket.id)
    if old_agent_id:
        await notify(db, old_agent_id, "ticket_reassigned", "Ticket reassigned",
                     f"Ticket {ticket.ticket_number} was reassigned to another agent.", ticket.id)
    await push_open_counts(db, [a for a in (old_agent_id, agent.id) if a])
    return ticket
