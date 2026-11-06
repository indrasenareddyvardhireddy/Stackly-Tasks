from sqlalchemy import Column, DateTime, Enum as SAEnum, Numeric

from app.database import Base  # noqa: F401
from app.utils.common import utcnow

# DECIMAL(12, 2) for every money column
Money = Numeric(12, 2)


def enum_col(enum_cls):
    """Stored as VARCHAR holding the human readable value (e.g. 'P2P Transfer')."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=30,
        create_constraint=False,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


class TimestampMixin:
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
