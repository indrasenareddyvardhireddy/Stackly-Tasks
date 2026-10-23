from datetime import datetime


def now() -> datetime:
    """Naive server-local time used everywhere (documented assumption)."""
    return datetime.now()
