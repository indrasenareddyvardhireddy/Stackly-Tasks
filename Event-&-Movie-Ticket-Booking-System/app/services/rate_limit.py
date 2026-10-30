from fastapi import HTTPException

from app.redis_client import redis_client as r


def check_rate_limit(key: str, limit: int, window_seconds: int = 60):
    """Fixed-window limiter. Raises 429 with the number of seconds to wait."""
    count = r.incr(key)
    if count == 1:
        r.expire(key, window_seconds)
    ttl = r.ttl(key)
    if ttl is None or ttl < 0:          # safety: key without expiry
        r.expire(key, window_seconds)
        ttl = window_seconds
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please wait {ttl} seconds before trying again.",
            headers={"Retry-After": str(ttl)},
        )
