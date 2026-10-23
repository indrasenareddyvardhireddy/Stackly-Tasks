"""Connection manager. Services are synchronous (threadpool / scheduler threads),
so `push` is thread-safe and schedules the send on the server's event loop."""
import asyncio
from collections import defaultdict
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[int, Set[WebSocket]]] = {
            "orders": defaultdict(set), "restaurants": defaultdict(set), "partners": defaultdict(set)}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def connect(self, room: str, key: int, ws: WebSocket):
        self.rooms[room][key].add(ws)

    def disconnect(self, room: str, key: int, ws: WebSocket):
        sockets = self.rooms[room].get(key)
        if sockets is not None:
            sockets.discard(ws)
            if not sockets:
                self.rooms[room].pop(key, None)

    async def _send(self, room: str, key: int, data: Any):
        for ws in list(self.rooms[room].get(key, ())):
            try:
                await ws.send_json(data)
            except Exception:  # dead connection -> drop silently
                self.disconnect(room, key, ws)

    def push(self, room: str, key: int, data: Any):
        """Fire-and-forget; safe from any thread. Never raises."""
        if self.loop is None or not self.rooms[room].get(key):
            return
        try:
            asyncio.run_coroutine_threadsafe(self._send(room, key, data), self.loop)
        except Exception:
            pass


manager = ConnectionManager()
