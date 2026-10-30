from datetime import datetime


def now() -> datetime:
    """Naive server-local 'now' without microseconds (MySQL DATETIME has second precision)."""
    return datetime.now().replace(microsecond=0)
