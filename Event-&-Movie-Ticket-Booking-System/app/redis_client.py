import redis

from app.config import settings

# decode_responses=True -> all values come back as str
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis_client
