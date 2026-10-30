import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import authenticate_token
from app.database import SessionLocal
from app.models.event import Show
from app.services import seat_service
from app.websockets.manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


def _authenticate(token: Optional[str]) -> Optional[int]:
    if not token:
        return None
    db = SessionLocal()
    try:
        user = authenticate_token(token, db)
        return user.id if user else None
    finally:
        db.close()


def _load_seat_map(show_id: int, user_id: int):
    db = SessionLocal()
    try:
        show = db.get(Show, show_id)
        if not show:
            return None
        return {"status": show.status, "seats": seat_service.apply_viewer(seat_service.get_seat_states(db, show), user_id)}
    finally:
        db.close()


@router.websocket("/ws/shows/{show_id}/seats")
async def seat_map_socket(websocket: WebSocket, show_id: int, token: Optional[str] = Query(default=None)):
    """Live seat map. Connect with  ws://host/ws/shows/{show_id}/seats?token=<access_token>"""
    await websocket.accept()
    user_id = await run_in_threadpool(_authenticate, token)
    if user_id is None:
        await websocket.close(code=4401, reason="Invalid or expired token")
        return

    # register first, then load the map, so no update can fall into a gap
    manager.register_show(show_id, websocket, user_id)
    try:
        data = await run_in_threadpool(_load_seat_map, show_id, user_id)
        if data is None:
            await websocket.close(code=4404, reason="Show not found")
            return
        await websocket.send_json(jsonable_encoder({
            "type": "seat_map", "show_id": show_id, "show_status": data["status"], "seats": data["seats"]}))
        while True:                                   # keep the socket open; ignore client messages
            text = await websocket.receive_text()
            if text.strip().lower() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Seat map socket error")
    finally:
        manager.unregister_show(show_id, websocket)   # always clean up, never raises


@router.websocket("/ws/notifications")
async def notifications_socket(websocket: WebSocket, token: Optional[str] = Query(default=None)):
    """Personal live notifications (show cancelled, refunds, waitlist)."""
    await websocket.accept()
    user_id = await run_in_threadpool(_authenticate, token)
    if user_id is None:
        await websocket.close(code=4401, reason="Invalid or expired token")
        return
    manager.register_user(user_id, websocket)
    try:
        await websocket.send_json({"type": "connected", "message": "Notifications connected"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Notification socket error")
    finally:
        manager.unregister_user(user_id, websocket)
