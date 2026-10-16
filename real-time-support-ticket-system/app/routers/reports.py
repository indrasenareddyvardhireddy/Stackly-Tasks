from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.database import get_db
from app.models import AgentProfile, Category, Feedback, Ticket, User
from app.models.enums import FINISHED_STATUSES, Availability, Priority, Role, TicketStatus

router = APIRouter(
    prefix="/reports", tags=["Reports"], dependencies=[Depends(require_roles(Role.ADMIN))]
)


def _range(col, from_date: Optional[date], to_date: Optional[date]):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must not be after to_date")
    conds = []
    if from_date:
        conds.append(col >= datetime.combine(from_date, time.min))
    if to_date:
        conds.append(col < datetime.combine(to_date + timedelta(days=1), time.min))
    return conds


def _f(value, nd: int = 2):
    return None if value is None else round(float(value), nd)


def _minutes(seconds_avg):
    return None if seconds_avg is None else round(float(seconds_avg) / 60, 2)


FIRST_RESPONSE_SECS = func.timestampdiff(literal_column("SECOND"), Ticket.created_at, Ticket.first_response_at)
# resolution time excludes time the ticket spent waiting on the customer / resolved
RESOLUTION_SECS = (
    func.timestampdiff(literal_column("SECOND"), Ticket.created_at, Ticket.resolved_at) - Ticket.paused_seconds
)


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Ticket.id)))).scalar_one()
    by_status = {s.value: 0 for s in TicketStatus}
    for status, count in (await db.execute(select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status))).all():
        by_status[status.value] = count
    unassigned = (
        await db.execute(
            select(func.count(Ticket.id)).where(Ticket.assigned_agent_id.is_(None), Ticket.status == TicketStatus.OPEN)
        )
    ).scalar_one()
    breached = (await db.execute(select(func.count(Ticket.id)).where(Ticket.sla_breached.is_(True)))).scalar_one()
    online = (
        await db.execute(
            select(func.count(User.id))
            .join(AgentProfile, AgentProfile.user_id == User.id)
            .where(User.is_active.is_(True), AgentProfile.availability == Availability.ONLINE)
        )
    ).scalar_one()
    return {
        "total_tickets": total,
        "tickets_by_status": by_status,
        "unassigned_tickets": unassigned,
        "sla_breached_tickets": breached,
        "agents_online": online,
    }


@router.get("/agent-performance")
async def agent_performance(
    from_date: Optional[date] = None, to_date: Optional[date] = None, db: AsyncSession = Depends(get_db)
):
    """Per agent, for tickets created in the date range."""
    join_cond = and_(Ticket.assigned_agent_id == User.id, *_range(Ticket.created_at, from_date, to_date))
    resolved_flag = case((Ticket.status.in_(FINISHED_STATUSES), 1), else_=0)
    breached_flag = case((Ticket.sla_breached.is_(True), 1), else_=0)
    stmt = (
        select(
            User.id, User.name,
            func.count(Ticket.id),
            func.coalesce(func.sum(resolved_flag), 0),
            func.avg(FIRST_RESPONSE_SECS),
            func.avg(case((Ticket.resolved_at.isnot(None), RESOLUTION_SECS))),
            func.coalesce(func.sum(breached_flag), 0),
            func.avg(Feedback.rating),
        )
        .select_from(User)
        .outerjoin(Ticket, join_cond)
        .outerjoin(Feedback, Feedback.ticket_id == Ticket.id)
        .where(User.role == Role.AGENT)
        .group_by(User.id, User.name)
        .order_by(User.id)
    )
    result = []
    for uid, name, total, resolved, fr, res, breached, rating in (await db.execute(stmt)).all():
        result.append({
            "agent_id": uid,
            "agent_name": name,
            "tickets_assigned": total,
            "tickets_resolved": int(resolved),
            "avg_first_response_minutes": _minutes(fr),
            "avg_resolution_minutes": _minutes(res),
            "sla_breach_percentage": round(float(breached) / total * 100, 2) if total else 0.0,
            "avg_rating": _f(rating),
        })
    return result


@router.get("/category-summary")
async def category_summary(
    from_date: Optional[date] = None, to_date: Optional[date] = None, db: AsyncSession = Depends(get_db)
):
    join_cond = and_(Ticket.category_id == Category.id, *_range(Ticket.created_at, from_date, to_date))
    stmt = (
        select(
            Category.id, Category.category_name, func.count(Ticket.id),
            func.avg(case((Ticket.resolved_at.isnot(None), RESOLUTION_SECS))),
        )
        .select_from(Category)
        .outerjoin(Ticket, join_cond)
        .group_by(Category.id, Category.category_name)
        .order_by(Category.id)
    )
    return [
        {"category_id": cid, "category_name": name, "ticket_count": count, "avg_resolution_minutes": _minutes(avg)}
        for cid, name, count, avg in (await db.execute(stmt)).all()
    ]


@router.get("/sla-summary")
async def sla_summary(
    from_date: Optional[date] = None, to_date: Optional[date] = None, db: AsyncSession = Depends(get_db)
):
    """met = Resolved/Closed tickets that never breached; breached = any ticket flagged sla_breached."""
    conds = _range(Ticket.created_at, from_date, to_date)
    met_flag = case((and_(Ticket.status.in_(FINISHED_STATUSES), Ticket.sla_breached.is_(False)), 1), else_=0)
    breached_flag = case((Ticket.sla_breached.is_(True), 1), else_=0)
    stmt = select(
        Ticket.priority, func.count(Ticket.id), func.sum(met_flag), func.sum(breached_flag)
    ).group_by(Ticket.priority)
    if conds:
        stmt = stmt.where(*conds)
    data = {p.value: {"priority": p.value, "total_tickets": 0, "sla_met": 0, "sla_breached": 0} for p in Priority}
    for priority, total, met, breached in (await db.execute(stmt)).all():
        data[priority.value] = {
            "priority": priority.value, "total_tickets": total, "sla_met": int(met or 0), "sla_breached": int(breached or 0),
        }
    return list(data.values())


@router.get("/customer-satisfaction")
async def customer_satisfaction(
    from_date: Optional[date] = None, to_date: Optional[date] = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(Feedback.rating, func.count(Feedback.id)).group_by(Feedback.rating)
    conds = _range(Feedback.created_at, from_date, to_date)
    if conds:
        stmt = stmt.where(*conds)
    distribution = {str(i): 0 for i in range(1, 6)}
    total = weighted = 0
    for rating, count in (await db.execute(stmt)).all():
        distribution[str(rating)] = count
        total += count
        weighted += rating * count
    return {
        "total_feedback": total,
        "average_rating": round(weighted / total, 2) if total else None,
        "rating_distribution": distribution,
    }
