from __future__ import annotations

from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field
)


class LeaveCreate(BaseModel):

    employee_id: int = Field(
        gt=0
    )

    leave_type: str = Field(
        pattern=r"^(Sick|Casual|Earned)$"
    )

    start_date: date

    end_date: date

    reason: str = Field(
        min_length=2,
        max_length=500
    )


class LeaveReject(BaseModel):

    rejection_reason: str = Field(
        min_length=2,
        max_length=500
    )


class LeaveResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    leave_id: int
    employee_id: int
    leave_type: str
    start_date: date
    end_date: date
    total_days: int
    reason: str
    status: str
    approved_by: int | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class LeaveBalanceResponse(BaseModel):

    employee_id: int
    year: int
    allocated: dict[str, int]
    approved_used: dict[str, int]
    remaining: dict[str, int]