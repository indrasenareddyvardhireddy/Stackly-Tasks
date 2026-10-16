import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from fastapi import WebSocket

from app.models.enums import Role

logger = logging.getLogger(__name__)


@dataclass
class ChatConn:
    ws: WebSocket
    user_id: int
    role: Role


class ChatManager:
    """Tracks connections per ticket room."""

    def __init__(self) -> None:
        self.rooms: Dict[int, List[ChatConn]] = {}

    def connect(self, ticket_id: int, ws: WebSocket, user_id: int, role: Role) -> None:
        self.rooms.setdefault(ticket_id, []).append(ChatConn(ws, user_id, role))

    def disconnect(self, ticket_id: int, ws: WebSocket) -> None:
        room = self.rooms.get(ticket_id)
        if not room:
            return
        self.rooms[ticket_id] = [c for c in room if c.ws is not ws]
        if not self.rooms[ticket_id]:
            del self.rooms[ticket_id]

    def is_connected(self, ticket_id: int, user_id: int) -> bool:
        return any(c.user_id == user_id for c in self.rooms.get(ticket_id, []))

    async def broadcast(
        self,
        ticket_id: int,
        payload: dict,
        internal_only: bool = False,
        exclude: Optional[WebSocket] = None,
    ) -> None:
        """Send to everyone in the room. internal_only=True skips customers (internal notes)."""
        dead = []
        for conn in list(self.rooms.get(ticket_id, [])):
            if internal_only and conn.role == Role.CUSTOMER:
                continue
            if exclude is not None and conn.ws is exclude:
                continue
            try:
                await conn.ws.send_json(payload)
            except Exception:
                dead.append(conn.ws)
        for ws in dead:
            self.disconnect(ticket_id, ws)


class NotificationManager:
    """Tracks /ws/notifications connections per user."""

    def __init__(self) -> None:
        self.connections: Dict[int, List[WebSocket]] = {}

    def connect(self, user_id: int, ws: WebSocket) -> None:
        self.connections.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: int, ws: WebSocket) -> None:
        conns = self.connections.get(user_id)
        if not conns:
            return
        self.connections[user_id] = [w for w in conns if w is not ws]
        if not self.connections[user_id]:
            del self.connections[user_id]

    async def send(self, user_id: int, payload: dict) -> None:
        dead = []
        for ws in list(self.connections.get(user_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)


chat_manager = ChatManager()
notification_manager = NotificationManager()
