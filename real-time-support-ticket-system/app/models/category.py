from typing import List, Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Priority, sa_enum
from app.models.user import agent_categories


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tickets: Mapped[List["Ticket"]] = relationship(back_populates="category")
    agents: Mapped[List["AgentProfile"]] = relationship(secondary=agent_categories, back_populates="categories")


class SLAPolicy(Base, TimestampMixin):
    __tablename__ = "sla_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    priority: Mapped[Priority] = mapped_column(sa_enum(Priority, "sla_priority"), unique=True, nullable=False)
    first_response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
