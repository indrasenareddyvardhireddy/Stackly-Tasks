from sqlalchemy import Column, DateTime, Numeric
from app.utils.timeutil import now

# Money columns come back as plain floats
Money = Numeric(10, 2, asdecimal=False)


class TimestampMixin:
    created_at = Column(DateTime, default=now, nullable=False)
    updated_at = Column(DateTime, default=now, onupdate=now, nullable=False)
