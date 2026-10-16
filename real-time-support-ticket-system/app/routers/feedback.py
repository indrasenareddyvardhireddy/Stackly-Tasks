from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models import Feedback, User
from app.models.enums import FINISHED_STATUSES, Role
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.services.ticket_service import get_accessible_ticket, get_ticket_or_404

router = APIRouter(prefix="/tickets", tags=["Feedback"])


@router.post("/{ticket_id}/feedback", response_model=FeedbackOut, status_code=201)
async def give_feedback(
    ticket_id: int, data: FeedbackCreate, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.CUSTOMER)),
):
    ticket = await get_ticket_or_404(db, ticket_id)
    if ticket.customer_id != user.id:
        raise HTTPException(status_code=403, detail="Only the ticket's customer can give feedback")
    if ticket.status not in FINISHED_STATUSES:
        raise HTTPException(status_code=400, detail="Feedback can only be given for Resolved or Closed tickets")
    existing = await db.execute(select(Feedback.id).where(Feedback.ticket_id == ticket_id))
    if existing.first():
        raise HTTPException(status_code=409, detail="Feedback was already submitted for this ticket")
    fb = Feedback(ticket_id=ticket_id, rating=data.rating, comment=data.comment)
    db.add(fb)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Feedback was already submitted for this ticket")
    return fb


@router.get("/{ticket_id}/feedback", response_model=FeedbackOut)
async def get_feedback(ticket_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await get_accessible_ticket(db, ticket_id, user)
    res = await db.execute(select(Feedback).where(Feedback.ticket_id == ticket_id))
    fb = res.scalar_one_or_none()
    if fb is None:
        raise HTTPException(status_code=404, detail="No feedback for this ticket")
    return fb
