from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Priority, Role, TicketStatus, sa_enum


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    subject: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[Priority] = mapped_column(
        sa_enum(Priority, "ticket_priority"), default=Priority.MEDIUM, nullable=False
    )
    status: Mapped[TicketStatus] = mapped_column(
        sa_enum(TicketStatus, "ticket_status"), default=TicketStatus.OPEN, nullable=False, index=True
    )
    assigned_agent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    first_response_due: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolution_due: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_response_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolution_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_response_escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolution_escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # SLA pause bookkeeping (time spent waiting on the customer / in Resolved is not counted)
    waiting_since: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    paused_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    customer: Mapped["User"] = relationship(back_populates="tickets", foreign_keys=[customer_id])
    agent: Mapped[Optional["User"]] = relationship(back_populates="assigned_tickets", foreign_keys=[assigned_agent_id])
    category: Mapped["Category"] = relationship(back_populates="tickets")
    messages: Mapped[List["Message"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")
    history: Mapped[List["TicketStatusHistory"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")
    feedback: Mapped[Optional["Feedback"]] = relationship(
        back_populates="ticket", uselist=False, cascade="all, delete-orphan"
    )


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sender_role: Mapped[Role] = mapped_column(sa_enum(Role, "user_role"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal_note: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="messages")


class TicketStatusHistory(Base, TimestampMixin):
    __tablename__ = "ticket_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    # status_change | assignment | priority_change | escalation
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    changed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    ticket: Mapped["Ticket"] = relationship(back_populates="history")


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ticket: Mapped["Ticket"] = relationship(back_populates="feedback")
