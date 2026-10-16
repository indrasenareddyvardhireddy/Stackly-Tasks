from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Message, User
from app.models.enums import Role
from app.schemas.message import MessageCreate, MessageOut
from app.services.chat_service import mark_read, post_message
from app.services.ticket_service import get_accessible_ticket

router = APIRouter(prefix="/tickets", tags=["Messages"])


@router.get("/{ticket_id}/messages", response_model=List[MessageOut])
async def list_messages(
    ticket_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Oldest first. Internal notes are never returned to customers."""
    ticket = await get_accessible_ticket(db, ticket_id, user)
    stmt = select(Message).where(Message.ticket_id == ticket_id)
    if user.role == Role.CUSTOMER:
        stmt = stmt.where(Message.is_internal_note.is_(False))
    messages = (
        await db.execute(stmt.order_by(Message.created_at.asc(), Message.id.asc()).offset(skip).limit(limit))
    ).scalars().all()
    await mark_read(db, ticket, user)
    await db.commit()
    return messages


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=201)
async def send_message(
    ticket_id: int, data: MessageCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    ticket = await get_accessible_ticket(db, ticket_id, user)
    return await post_message(db, ticket, user, data.message, data.is_internal_note)
