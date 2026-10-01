from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.leave_request import LeaveRequest


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True,
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        Enum(
            "Admin",
            "HR",
            "Employee",
            name="user_role"
        ),
        nullable=False,
        default="Employee"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
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
    # USER -> EMPLOYEE
    # --------------------------------------------------

    employee: Mapped["Employee | None"] = relationship(
        "Employee",
        back_populates="user",
        uselist=False
    )

    # --------------------------------------------------
    # USER -> LEAVE REQUESTS APPROVED/REJECTED
    # --------------------------------------------------

    leaves_approved: Mapped[list["LeaveRequest"]] = relationship(
        "LeaveRequest",
        foreign_keys="LeaveRequest.approved_by",
        back_populates="approver"
    )