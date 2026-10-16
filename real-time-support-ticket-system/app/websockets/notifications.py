import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from app.auth.dependencies import user_from_token
from app.database import AsyncSessionLocal
from app.models import Notification
from app.services.notification_service import open_count_for
from app.websockets.manager import notification_manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket, token: Optional[str] = Query(default=None)):
    await websocket.accept()
    async with AsyncSessionLocal() as db:
        user = await user_from_token(db, token)
        if user is None:
            await websocket.close(code=4401, reason="Invalid or expired token")
            return
        unread = (
            await db.execute(
                select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.is_read.is_(False))
            )
        ).scalar_one()
        open_count = await open_count_for(db, user.id, user.role)
        user_id = user.id

    notification_manager.connect(user_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "unread_count": unread})
        if open_count is not None:
            await websocket.send_json({"type": "open_tickets_count", "count": open_count})
        while True:
            text = await websocket.receive_text()  # keeps the socket open; supports "ping"
            if text.strip().lower() == "ping":
                await websocket.send_json({"type": "pong"})
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        logger.exception("Unexpected error in notifications websocket")
    finally:
        notification_manager.disconnect(user_id, websocket)
