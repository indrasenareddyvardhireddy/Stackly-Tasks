from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.auth.security import hash_password
from app.database import get_db
from app.models import AgentProfile, Category, Ticket, User
from app.models.enums import Availability, Role, TicketStatus
from app.schemas.agent import AgentCreate, AgentOut, AgentUpdate, AvailabilityUpdate, CategoryBrief
from app.schemas.ticket import TicketOut
from app.services.assignment_service import assign_pending_tickets

router = APIRouter(prefix="/agents", tags=["Agents"])


def agent_to_out(user: User) -> AgentOut:
    p = user.agent_profile
    return AgentOut(
        user_id=user.id, name=user.name, email=user.email,
        categories=[CategoryBrief.model_validate(c) for c in p.categories],
        availability=p.availability, max_open_tickets=p.max_open_tickets,
        is_active=user.is_active, created_at=user.created_at,
    )


async def _load_categories(db: AsyncSession, ids: List[int]) -> List[Category]:
    ids = list(set(ids))
    if not ids:
        return []
    cats = (await db.execute(select(Category).where(Category.id.in_(ids)))).scalars().all()
    if len(cats) != len(ids):
        missing = sorted(set(ids) - {c.id for c in cats})
        raise HTTPException(status_code=404, detail=f"Categories not found: {missing}")
    return list(cats)


@router.post("", response_model=AgentOut, status_code=201, summary="Create an agent (Admin only)")
async def create_agent(
    data: AgentCreate, db: AsyncSession = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))
):
    email = data.email.lower()
    if (await db.execute(select(User.id).where(User.email == email))).first():
        raise HTTPException(status_code=409, detail="Email is already registered")
    cats = await _load_categories(db, data.category_ids)
    user = User(name=data.name, email=email, hashed_password=hash_password(data.password), role=Role.AGENT, is_active=True)
    user.agent_profile = AgentProfile(
        availability=data.availability, max_open_tickets=data.max_open_tickets, categories=cats
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered")
    if data.availability == Availability.ONLINE:
        await assign_pending_tickets(db)
    await db.commit()
    return agent_to_out(user)


@router.get("", response_model=List[AgentOut], summary="List agents (Admin only)")
async def list_agents(
    availability: Optional[Availability] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    stmt = select(User).join(AgentProfile, AgentProfile.user_id == User.id).where(User.role == Role.AGENT)
    if availability is not None:
        stmt = stmt.where(AgentProfile.availability == availability)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    users = (await db.execute(stmt.order_by(User.id).offset(skip).limit(limit))).scalars().all()
    return [agent_to_out(u) for u in users]


# NOTE: /me routes must be declared before /{agent_id}
@router.put("/me/availability", response_model=AgentOut)
async def set_my_availability(
    data: AvailabilityUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(require_roles(Role.AGENT))
):
    if user.agent_profile is None:
        raise HTTPException(status_code=404, detail="Agent profile not found")
    user.agent_profile.availability = data.availability
    await db.flush()
    if data.availability == Availability.ONLINE:
        await assign_pending_tickets(db)  # pick up tickets that were waiting for an agent
    await db.commit()
    return agent_to_out(user)


@router.get("/me/tickets", response_model=List[TicketOut])
async def my_tickets(
    status: Optional[TicketStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.AGENT)),
):
    stmt = select(Ticket).where(Ticket.assigned_agent_id == user.id)
    if status is not None:
        stmt = stmt.where(Ticket.status == status)
    stmt = stmt.order_by(Ticket.created_at.desc(), Ticket.id.desc()).offset(skip).limit(limit)
    return (await db.execute(stmt)).scalars().all()


@router.put("/{agent_id}", response_model=AgentOut, summary="Update an agent (Admin only)")
async def update_agent(
    agent_id: int, data: AgentUpdate, db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    user = await db.get(User, agent_id)
    if user is None or user.role != Role.AGENT or user.agent_profile is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    fields = data.model_dump(exclude_unset=True)

    if "email" in fields and fields["email"]:
        email = fields["email"].lower()
        taken = await db.execute(select(User.id).where(User.email == email, User.id != user.id))
        if taken.first():
            raise HTTPException(status_code=409, detail="Email is already registered")
        user.email = email
    if fields.get("name"):
        user.name = fields["name"]
    if fields.get("is_active") is not None:
        user.is_active = fields["is_active"]
    if fields.get("category_ids") is not None:
        user.agent_profile.categories = await _load_categories(db, fields["category_ids"])
    if fields.get("max_open_tickets") is not None:
        user.agent_profile.max_open_tickets = fields["max_open_tickets"]
    if fields.get("availability") is not None:
        user.agent_profile.availability = fields["availability"]

    await db.flush()
    if user.is_active and user.agent_profile.availability == Availability.ONLINE:
        await assign_pending_tickets(db)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered")
    return agent_to_out(user)
