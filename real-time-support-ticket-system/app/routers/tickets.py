from datetime import date, datetime, time, timedelta
from typing import List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models import Ticket, TicketStatusHistory, User
from app.models.enums import Priority, Role, TicketStatus
from app.schemas.ticket import AssignRequest, HistoryOut, PriorityUpdate, StatusUpdate, TicketCreate, TicketOut
from app.services.email_service import send_email
from app.services.ticket_service import (
    can_manage_ticket, change_priority, change_status, create_ticket, get_accessible_ticket,
    get_ticket_or_404, reassign_ticket, reopen_ticket,
)

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.post("", response_model=TicketOut, status_code=201)
async def create(
    data: TicketCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.CUSTOMER)),
):
    ticket = await create_ticket(db, user, data)
    await db.commit()
    background_tasks.add_task(
        send_email, user.email, f"[{ticket.ticket_number}] Ticket created",
        f"Hi {user.name},\n\nWe received your ticket \"{ticket.subject}\" ({ticket.ticket_number}).\n"
        f"Priority: {ticket.priority.value}. We'll get back to you shortly.",
    )
    return ticket


@router.get("", response_model=List[TicketOut])
async def list_tickets(
    ticket_number: Optional[str] = None,
    subject: Optional[str] = Query(None, description="Partial match"),
    status: Optional[TicketStatus] = None,
    priority: Optional[Priority] = None,
    category_id: Optional[int] = None,
    assigned_agent_id: Optional[int] = None,
    sla_breached: Optional[bool] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    sort_by: Literal["created_at", "updated_at", "priority", "status", "resolution_due", "first_response_due"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Ticket)
    # role-based scoping
    if user.role == Role.CUSTOMER:
        stmt = stmt.where(Ticket.customer_id == user.id)
    elif user.role == Role.AGENT:
        stmt = stmt.where(Ticket.assigned_agent_id == user.id)

    if ticket_number:
        stmt = stmt.where(Ticket.ticket_number == ticket_number)
    if subject:
        stmt = stmt.where(Ticket.subject.ilike(f"%{subject}%"))
    if status is not None:
        stmt = stmt.where(Ticket.status == status)
    if priority is not None:
        stmt = stmt.where(Ticket.priority == priority)
    if category_id is not None:
        stmt = stmt.where(Ticket.category_id == category_id)
    if assigned_agent_id is not None:
        stmt = stmt.where(Ticket.assigned_agent_id == assigned_agent_id)
    if sla_breached is not None:
        stmt = stmt.where(Ticket.sla_breached.is_(sla_breached))
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must not be after to_date")
    if from_date:
        stmt = stmt.where(Ticket.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        stmt = stmt.where(Ticket.created_at < datetime.combine(to_date + timedelta(days=1), time.min))

    col = getattr(Ticket, sort_by)
    stmt = stmt.order_by(col.asc() if order == "asc" else col.desc(), Ticket.id.desc()).offset(skip).limit(limit)
    return (await db.execute(stmt)).scalars().all()


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return await get_accessible_ticket(db, ticket_id, user)


@router.put("/{ticket_id}/status", response_model=TicketOut)
async def update_status(
    ticket_id: int,
    data: StatusUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = await get_ticket_or_404(db, ticket_id)
    if not can_manage_ticket(user, ticket):
        raise HTTPException(status_code=403, detail="Only the assigned agent or an admin can change the status")
    await change_status(db, ticket, data.status, user, data.note)
    customer = await db.get(User, ticket.customer_id)
    await db.commit()
    if data.status == TicketStatus.RESOLVED and customer:
        background_tasks.add_task(
            send_email, customer.email, f"[{ticket.ticket_number}] Ticket resolved",
            f"Hi {customer.name},\n\nYour ticket \"{ticket.subject}\" was marked as resolved. "
            "You can reopen it within 7 days if the problem persists.",
        )
    return ticket


@router.put("/{ticket_id}/priority", response_model=TicketOut)
async def update_priority(
    ticket_id: int, data: PriorityUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    ticket = await get_ticket_or_404(db, ticket_id)
    if not can_manage_ticket(user, ticket):
        raise HTTPException(status_code=403, detail="Only the assigned agent or an admin can change the priority")
    await change_priority(db, ticket, data.priority, user)
    await db.commit()
    return ticket


@router.put("/{ticket_id}/reopen", response_model=TicketOut)
async def reopen(
    ticket_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles(Role.CUSTOMER))
):
    ticket = await get_ticket_or_404(db, ticket_id)
    await reopen_ticket(db, ticket, user)
    await db.commit()
    return ticket


@router.get("/{ticket_id}/history", response_model=List[HistoryOut])
async def history(ticket_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_accessible_ticket(db, ticket_id, user)
    stmt = (
        select(TicketStatusHistory)
        .where(TicketStatusHistory.ticket_id == ticket_id)
        .order_by(TicketStatusHistory.created_at.asc(), TicketStatusHistory.id.asc())
    )
    return (await db.execute(stmt)).scalars().all()


@router.put("/{ticket_id}/assign", response_model=TicketOut, summary="Assign / reassign a ticket (Admin only)")
async def assign(
    ticket_id: int, data: AssignRequest, db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    ticket = await get_ticket_or_404(db, ticket_id)
    await reassign_ticket(db, ticket, data.agent_id, admin)
    await db.commit()
    return ticket
