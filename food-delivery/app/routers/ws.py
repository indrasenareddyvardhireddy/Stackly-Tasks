import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.auth.security import ADMIN, OWNER, PARTNER, user_from_token
from app.database import SessionLocal
from app.models import DeliveryOffer, DeliveryPartner, Order
from app.routers.partners import save_location
from app.services.assignment_service import offer_payload
from app.services.order_service import can_view_order, tracking_payload
from app.utils.timeutil import now
from app.websockets.manager import manager

router = APIRouter(tags=["WebSockets"])


def _authenticate(token: str, roles=None):
    """Returns (user_id, role) or None. Session is closed immediately (no DB held while connected)."""
    db = SessionLocal()
    try:
        user = user_from_token(token or "", db)
        if user is None or (roles and user.role not in roles):
            return None
        if user.role in (OWNER, PARTNER) and not user.is_approved:
            return None
        return user
    finally:
        db.close()


async def _reject(ws: WebSocket, reason: str):
    await ws.accept()
    await ws.close(code=4401, reason=reason)


def _order_snapshot(order_id: int, token: str):
    db = SessionLocal()
    try:
        user = user_from_token(token or "", db)
        if user is None:
            return None, "Invalid or expired token"
        order = db.get(Order, order_id)
        if order is None:
            return None, "Order not found"
        if not can_view_order(user, order):
            return None, "Not allowed to track this order"
        return tracking_payload(order, "Connected"), None
    finally:
        db.close()


@router.websocket("/ws/orders/{order_id}")
async def ws_order(ws: WebSocket, order_id: int, token: str = ""):
    snapshot, error = await run_in_threadpool(_order_snapshot, order_id, token)
    if error:
        return await _reject(ws, error)
    await ws.accept()
    manager.connect("orders", order_id, ws)
    try:
        await ws.send_json(snapshot)
        while True:
            await ws.receive_text()  # keep-alive; client messages ignored
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect("orders", order_id, ws)


@router.websocket("/ws/restaurant")
async def ws_restaurant(ws: WebSocket, token: str = ""):
    user = await run_in_threadpool(_authenticate, token, [OWNER])
    if not user:
        return await _reject(ws, "Unauthorized")
    uid = user.id
    await ws.accept()
    manager.connect("restaurants", uid, ws)
    try:
        await ws.send_json({"type": "connected", "message": "Listening for new orders"})
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        manager.disconnect("restaurants", uid, ws)


def _pending_offers(user_id: int):
    db = SessionLocal()
    try:
        p = db.query(DeliveryPartner).filter(DeliveryPartner.user_id == user_id).first()
        offers = db.query(DeliveryOffer).filter(DeliveryOffer.partner_id == p.id, DeliveryOffer.status == "Pending",
                                                DeliveryOffer.expires_at > now()).all() if p else []
        return [offer_payload(o, p) for o in offers]
    finally:
        db.close()


def _save_location(user_id: int, lat: float, lng: float):
    db = SessionLocal()
    try:
        from app.models import User
        return save_location(db, db.get(User, user_id), lat, lng)
    finally:
        db.close()


@router.websocket("/ws/partner")
async def ws_partner(ws: WebSocket, token: str = ""):
    user = await run_in_threadpool(_authenticate, token, [PARTNER])
    if not user:
        return await _reject(ws, "Unauthorized")
    uid = user.id
    await ws.accept()
    manager.connect("partners", uid, ws)
    try:
        await ws.send_json({"type": "connected", "pending_offers": await run_in_threadpool(_pending_offers, uid)})
        while True:
            raw = await ws.receive_text()
            try:  # partner may send {"type":"location","latitude":..,"longitude":..} every 5-10 s
                msg = json.loads(raw)
                if msg.get("type") == "location":
                    lat, lng = float(msg["latitude"]), float(msg["longitude"])
                    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                        raise ValueError
                    await run_in_threadpool(_save_location, uid, lat, lng)
                    await ws.send_json({"type": "location_saved"})
            except (ValueError, KeyError, TypeError):
                await ws.send_json({"type": "error", "message": "Invalid message"})
    except Exception:
        pass
    finally:
        manager.disconnect("partners", uid, ws)


@router.get("/tracking-test", include_in_schema=False)
def tracking_test():
    return FileResponse("static/tracking_test.html")
