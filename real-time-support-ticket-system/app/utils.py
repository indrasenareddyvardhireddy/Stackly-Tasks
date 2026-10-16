from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC datetime (all DateTime columns store naive UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
