import hashlib
import json
import logging
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder

from app.config import settings
from app.redis_client import redis_client as r

logger = logging.getLogger(__name__)
PREFIX = "cache:events:"


def make_key(kind: str, scope: str, params: dict) -> str:
    digest = hashlib.md5(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()
    return f"{PREFIX}{kind}:{scope}:{digest}"


def cache_get(key: str) -> Optional[Any]:
    try:
        value = r.get(key)
        return json.loads(value) if value else None
    except Exception:
        logger.exception("Cache read failed")
        return None


def cache_set(key: str, data: Any, ttl: int = settings.EVENT_CACHE_TTL_SECONDS):
    try:
        r.set(key, json.dumps(jsonable_encoder(data)), ex=ttl)
    except Exception:
        logger.exception("Cache write failed")


def clear_event_cache():
    """Called whenever an event or show is created / updated / cancelled."""
    try:
        for key in r.scan_iter(match=f"{PREFIX}*", count=200):
            r.delete(key)
    except Exception:
        logger.exception("Cache clear failed")
