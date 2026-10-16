import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.auth.dependencies import user_from_token
from app.database import AsyncSessionLocal
from app.models import Ticket, User
from app.schemas.message import MessageOut
from app.services.chat_service import mark_read, post_message, recent_messages
from app.services.ticket_service import can_access_ticket
from app.websockets.manager import chat_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# Close codes: 4401 invalid/expired token, 4403 not allowed on this ticket, 4404 ticket not found


@router.websocket("/ws/tickets/{ticket_id}")
async def ticket_chat(websocket: WebSocket, ticket_id: int, token: Optional[str] = Query(default=None)):
    await websocket.accept()
    async with AsyncSessionLocal() as db:
        user = await user_from_token(db, token)
        if user is None:
            await websocket.close(code=4401, reason="Invalid or expired token")
            return
        ticket = await db.get(Ticket, ticket_id)
        if ticket is None:
            await websocket.close(code=4404, reason="Ticket not found")
            return
        if not can_access_ticket(user, ticket):
            await websocket.close(code=4403, reason="You cannot join this ticket's chat")
            return
        await mark_read(db, ticket, user)  # the other side's messages are now read
        history = await recent_messages(db, ticket_id, user, 50)
        await db.commit()
        history_payload = [MessageOut.model_validate(m).model_dump(mode="json") for m in history]
        user_id = user.id

    chat_manager.connect(ticket_id, websocket, user_id, user.role)
    try:
        await websocket.send_json({"type": "history", "messages": history_payload})
        while True:
            raw = await websocket.receive_text()
            await _handle_incoming(websocket, ticket_id, user_id, raw)
    except (WebSocketDisconnect, RuntimeError):
        pass  # client went away; cleanup happens in finally
    except Exception:
        logger.exception("Unexpected error in chat websocket")
    finally:
        chat_manager.disconnect(ticket_id, websocket)


async def _handle_incoming(ws: WebSocket, ticket_id: int, user_id: int, raw: str) -> None:
    try:
        data = json.loads(raw)
    except ValueError:
        await ws.send_json({"type": "error", "detail": "Invalid JSON"})
        return
    if not isinstance(data, dict):
        await ws.send_json({"type": "error", "detail": "Expected a JSON object"})
        return

    async with AsyncSessionLocal() as db:
        # re-check on every event: the ticket may have been reassigned or the user deactivated
        user = await db.get(User, user_id)
        ticket = await db.get(Ticket, ticket_id)
        if user is None or not user.is_active or ticket is None or not can_access_ticket(user, ticket):
            await ws.close(code=4403, reason="Access to this ticket was revoked")
            raise WebSocketDisconnect(code=4403)

        if data.get("type") == "typing":
            # transient: broadcast only, never stored
            await chat_manager.broadcast(
                ticket_id,
                {
                    "type": "typing", "user_id": user.id, "role": user.role.value,
                    "is_typing": bool(data.get("is_typing", True)),
                    "text": f"{user.role.value} is typing...",
                },
                exclude=ws,
            )
            return

        text = data.get("message")
        if not isinstance(text, str):
            await ws.send_json({"type": "error", "detail": "'message' must be a string"})
            return
        try:
            await post_message(db, ticket, user, text, bool(data.get("is_internal_note", False)))
        except HTTPException as exc:
            await db.rollback()
            await ws.send_json({"type": "error", "detail": exc.detail})
