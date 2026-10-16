from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Availability, Role, sa_enum
from app.utils import utcnow

# Many-to-many: which categories an agent can handle (also carries timestamps)
agent_categories = Table(
    "agent_categories",
    Base.metadata,
    Column("agent_id", Integer, ForeignKey("agent_profiles.user_id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, nullable=False, default=utcnow, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now()),
)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(sa_enum(Role, "user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    agent_profile: Mapped[Optional["AgentProfile"]] = relationship(
        back_populates="user", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )
    tickets: Mapped[List["Ticket"]] = relationship(back_populates="customer", foreign_keys="Ticket.customer_id")
    assigned_tickets: Mapped[List["Ticket"]] = relationship(
        back_populates="agent", foreign_keys="Ticket.assigned_agent_id"
    )
    notifications: Mapped[List["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AgentProfile(Base, TimestampMixin):
    __tablename__ = "agent_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    availability: Mapped[Availability] = mapped_column(
        sa_enum(Availability, "availability"), default=Availability.OFFLINE, nullable=False
    )
    max_open_tickets: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    user: Mapped["User"] = relationship(back_populates="agent_profile")
    categories: Mapped[List["Category"]] = relationship(
        secondary=agent_categories, back_populates="agents", lazy="selectin"
    )
