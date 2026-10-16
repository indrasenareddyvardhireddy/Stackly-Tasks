from typing import List

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Ticket, User
from app.models.enums import Role, TicketStatus
from app.schemas.message import MessageOut
from app.services.notification_service import notify
from app.services.ticket_service import apply_status, record_first_response
from app.websockets.manager import chat_manager

MAX_LEN = 2000


def serialize(msg: Message) -> dict:
    return MessageOut.model_validate(msg).model_dump(mode="json")


async def recent_messages(db: AsyncSession, ticket_id: int, user: User, limit: int = 50) -> List[Message]:
    stmt = select(Message).where(Message.ticket_id == ticket_id)
    if user.role == Role.CUSTOMER:
        stmt = stmt.where(Message.is_internal_note.is_(False))
    stmt = stmt.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return list(reversed(rows))


async def mark_read(db: AsyncSession, ticket: Ticket, user: User) -> int:
    """Mark the *other side's* messages as read when `user` opens the chat."""
    stmt = update(Message).where(Message.ticket_id == ticket.id, Message.is_read.is_(False))
    if user.role == Role.CUSTOMER:
        stmt = stmt.where(Message.sender_role != Role.CUSTOMER, Message.is_internal_note.is_(False))
    else:
        stmt = stmt.where(Message.sender_role == Role.CUSTOMER)
    result = await db.execute(stmt.values(is_read=True).execution_options(synchronize_session=False))
    await db.flush()
    if result.rowcount:
        await chat_manager.broadcast(
            ticket.id,
            {"type": "read", "reader_id": user.id, "reader_role": user.role.value},
            internal_only=False,
        )
    return result.rowcount


async def post_message(db: AsyncSession, ticket: Ticket, user: User, text: str, is_internal: bool = False) -> Message:
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    if len(text) > MAX_LEN:
        raise HTTPException(status_code=422, detail=f"Message cannot exceed {MAX_LEN} characters")
    if is_internal and user.role == Role.CUSTOMER:
        raise HTTPException(status_code=403, detail="Customers cannot send internal notes")
    if user.role == Role.CUSTOMER and ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=400, detail="This ticket is closed; you cannot send messages")

    msg = Message(
        ticket_id=ticket.id, sender_id=user.id, sender_role=user.role,
        message=text, is_internal_note=is_internal, is_read=False,
    )
    db.add(msg)
    await db.flush()

    if user.role == Role.AGENT and not is_internal:
        if ticket.first_response_at is None:
            await record_first_response(db, ticket)
        if ticket.status == TicketStatus.ASSIGNED:
            await apply_status(db, ticket, TicketStatus.IN_PROGRESS, user.id, "Agent replied", notify_customer=False)
    elif user.role == Role.CUSTOMER and ticket.status == TicketStatus.WAITING:
        await apply_status(db, ticket, TicketStatus.IN_PROGRESS, user.id, "Customer replied", notify_customer=False)
    await db.commit()

    # live delivery to everyone in the room (internal notes never reach customers)
    await chat_manager.broadcast(ticket.id, {"type": "message", "data": serialize(msg)}, internal_only=is_internal)

    # "not in the chat" notifications
    if not is_internal:
        if user.role != Role.CUSTOMER and not chat_manager.is_connected(ticket.id, ticket.customer_id):
            await notify(db, ticket.customer_id, "new_reply", f"New reply on {ticket.ticket_number}",
                         "Our support team replied to your ticket.", ticket.id)
        elif user.role == Role.CUSTOMER and ticket.assigned_agent_id and not chat_manager.is_connected(
            ticket.id, ticket.assigned_agent_id
        ):
            await notify(db, ticket.assigned_agent_id, "new_reply", f"Customer replied on {ticket.ticket_number}",
                         "The customer sent a new message.", ticket.id)
    await db.commit()
    return msg
