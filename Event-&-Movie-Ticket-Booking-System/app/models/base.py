from sqlalchemy import Column, DateTime, func

from app.utils.time import now


class TimestampMixin:
    """created_at / updated_at on every table."""
    created_at = Column(DateTime, nullable=False, default=now, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, default=now, onupdate=now, server_default=func.now())
