from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.user import User


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    leave_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.employee_id"),
        nullable=False,
        index=True
    )

    leave_type: Mapped[str] = mapped_column(
        Enum(
            "Sick",
            "Casual",
            "Earned",
            name="leave_type"
        ),
        nullable=False
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    total_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        Enum(
            "Pending",
            "Approved",
            "Rejected",
            "Cancelled",
            name="leave_status"
        ),
        nullable=False,
        default="Pending"
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id"),
        nullable=True,
        index=True
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # --------------------------------------------------
    # LEAVE REQUEST -> EMPLOYEE
    # --------------------------------------------------

    employee: Mapped["Employee"] = relationship(
        "Employee",
        back_populates="leave_requests"
    )

    # --------------------------------------------------
    # LEAVE REQUEST -> APPROVING USER
    # --------------------------------------------------

    approver: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[approved_by],
        back_populates="leaves_approved"
    )