"""
Pushes 'Seat X is now Available' when a Redis seat lock expires (TTL hit 0).
Uses Redis keyspace notifications (expired events). Enabled automatically below; if your Redis
forbids CONFIG SET start it with:  redis-server --notify-keyspace-events Ex
"""
import logging
import re
import threading
import time

from app.database import SessionLocal
from app.models.venue import Seat
from app.redis_client import redis_client
from app.services import seat_service
from app.websockets.manager import manager

logger = logging.getLogger(__name__)
_KEY = re.compile(r"^lock:show:(\d+):seat:(\d+)$")
_stop = threading.Event()
_thread = None


def enable_keyspace_notifications():
    try:
        current = redis_client.config_get("notify-keyspace-events").get("notify-keyspace-events", "")
        flags = set(current) | set("Ex")
        redis_client.config_set("notify-keyspace-events", "".join(sorted(flags)))
    except Exception:
        logger.warning("Could not enable Redis keyspace notifications; start Redis with "
                       "--notify-keyspace-events Ex to get live lock-expiry pushes")


def _handle_expired(key: str):
    match = _KEY.match(key)
    if not match:
        return
    show_id, seat_id = int(match.group(1)), int(match.group(2))
    db = SessionLocal()
    try:
        seat = db.get(Seat, seat_id)
        if seat:
            manager.push_seat_changes(show_id, [seat_service.change(seat, "Available")])
    finally:
        db.close()


def _run():
    while not _stop.is_set():
        try:
            pubsub = redis_client.pubsub()
            pubsub.psubscribe("__keyevent@*__:expired")
            while not _stop.is_set():
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "pmessage":
                    _handle_expired(message["data"])
        except Exception:
            logger.exception("Expiry listener error - retrying in 3s")
            time.sleep(3)


def start_expiry_listener():
    global _thread
    _stop.clear()
    _thread = threading.Thread(target=_run, name="lock-expiry-listener", daemon=True)
    _thread.start()


def stop_expiry_listener():
    _stop.set()
