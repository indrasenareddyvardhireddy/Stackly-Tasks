from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.leave_request import LeaveRequest
    from app.models.user import User


class Employee(Base):
    __tablename__ = "employees"

    employee_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    # Links employee to login user
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id"),
        unique=True,
        nullable=False,
        index=True
    )

    employee_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        index=True,
        nullable=False
    )

    phone: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.department_id"),
        nullable=False,
        index=True
    )

    designation: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    salary: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    date_of_joining: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    employment_type: Mapped[str] = mapped_column(
        Enum(
            "Full-Time",
            "Part-Time",
            "Intern",
            "Contract",
            name="employment_type"
        ),
        nullable=False
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

    # Employee -> User
    user: Mapped["User"] = relationship(
        "User",
        back_populates="employee",
        uselist=False
    )

    # Employee -> Department
    department: Mapped["Department"] = relationship(
        "Department",
        back_populates="employees"
    )

    # Employee -> Leave Requests
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(
        "LeaveRequest",
        back_populates="employee"
    )