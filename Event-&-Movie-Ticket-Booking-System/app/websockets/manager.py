import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Keeps the open WebSocket connections.
      * show_conns : viewers of a show's seat map   {show_id: [(ws, user_id)]}
      * user_conns : personal notification sockets  {user_id: [ws]}

    All dictionaries are touched only from the event loop thread. Code running in other threads
    (scheduler, request threadpool) uses the thread-safe `push_*` methods.
    """

    def __init__(self):
        self.show_conns: Dict[int, List[Tuple[WebSocket, int]]] = {}
        self.user_conns: Dict[int, List[WebSocket]] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    # ---------- registration (event loop thread) ----------
    def register_show(self, show_id: int, ws: WebSocket, user_id: int):
        self.show_conns.setdefault(show_id, []).append((ws, user_id))

    def unregister_show(self, show_id: int, ws: WebSocket):
        conns = self.show_conns.get(show_id, [])
        self.show_conns[show_id] = [c for c in conns if c[0] is not ws]
        if not self.show_conns[show_id]:
            self.show_conns.pop(show_id, None)

    def register_user(self, user_id: int, ws: WebSocket):
        self.user_conns.setdefault(user_id, []).append(ws)

    def unregister_user(self, user_id: int, ws: WebSocket):
        conns = [w for w in self.user_conns.get(user_id, []) if w is not ws]
        if conns:
            self.user_conns[user_id] = conns
        else:
            self.user_conns.pop(user_id, None)

    # ---------- async broadcasts ----------
    async def broadcast_seat_changes(self, show_id: int, changes: List[dict]):
        """changes: [{seat_id, label, status, locked_by}] -> each viewer gets 'Yours' for their own locks."""
        for ws, user_id in list(self.show_conns.get(show_id, [])):
            seats = []
            for c in changes:
                status = c["status"]
                if status == "Locked" and c.get("locked_by") == user_id:
                    status = "Yours"
                seats.append({"seat_id": c["seat_id"], "label": c["label"], "status": status})
            message = {
                "type": "seat_update",
                "show_id": show_id,
                "seats": seats,
                "message": "; ".join(f"Seat {s['label']} is now {s['status']}" for s in seats),
            }
            await self._safe_send_show(show_id, ws, message)

    async def broadcast_show_event(self, show_id: int, payload: dict):
        for ws, _ in list(self.show_conns.get(show_id, [])):
            await self._safe_send_show(show_id, ws, payload)

    async def send_to_user(self, user_id: int, payload: dict):
        for ws in list(self.user_conns.get(user_id, [])):
            try:
                await ws.send_json(jsonable_encoder(payload))
            except Exception:
                self.unregister_user(user_id, ws)

    async def _safe_send_show(self, show_id: int, ws: WebSocket, message: dict):
        try:
            await ws.send_json(jsonable_encoder(message))
        except Exception:
            # client vanished without a clean disconnect - drop it silently
            self.unregister_show(show_id, ws)

    # ---------- thread-safe entry points ----------
    def _submit(self, coro):
        if self.loop is not None and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self.loop)
        else:
            coro.close()   # no event loop yet (e.g. running a script / tests)

    def push_seat_changes(self, show_id: int, changes: List[dict]):
        if changes:
            self._submit(self.broadcast_seat_changes(show_id, changes))

    def push_show_event(self, show_id: int, payload: dict):
        self._submit(self.broadcast_show_event(show_id, payload))

    def push_user_notification(self, user_id: int, payload: dict):
        self._submit(self.send_to_user(user_id, payload))


manager = ConnectionManager()
