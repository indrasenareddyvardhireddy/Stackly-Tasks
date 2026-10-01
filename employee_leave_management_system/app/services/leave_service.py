from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func

from sqlalchemy.orm import Session

from app.models.leave_request import LeaveRequest


LEAVE_BALANCES = {
    "Sick": 12,
    "Casual": 10,
    "Earned": 15,
}


def calculate_weekdays(
    start_date: date,
    end_date: date
) -> int:

    days = 0

    current = start_date

    while current <= end_date:

        if current.weekday() < 5:
            days += 1

        current += timedelta(days=1)

    return days


def get_approved_usage(
    db: Session,
    employee_id: int,
    leave_type: str,
    year: int
) -> int:

    requests = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id
            == employee_id,

            LeaveRequest.leave_type
            == leave_type,

            LeaveRequest.status
            == "Approved",

            LeaveRequest.start_date
            <= date(year, 12, 31),

            LeaveRequest.end_date
            >= date(year, 1, 1)
        )
        .all()
    )


    total = 0


    for request in requests:

        overlap_start = max(
            request.start_date,
            date(year, 1, 1)
        )

        overlap_end = min(
            request.end_date,
            date(year, 12, 31)
        )


        if overlap_start <= overlap_end:

            total += calculate_weekdays(
                overlap_start,
                overlap_end
            )


    return total


def has_overlap(
    db: Session,
    employee_id: int,
    start_date: date,
    end_date: date,
    exclude_leave_id: int | None = None
) -> bool:

    query = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id
            == employee_id,

            LeaveRequest.status.in_(
                [
                    "Pending",
                    "Approved"
                ]
            ),

            LeaveRequest.start_date
            <= end_date,

            LeaveRequest.end_date
            >= start_date
        )
    )


    if exclude_leave_id is not None:

        query = query.filter(
            LeaveRequest.leave_id
            != exclude_leave_id
        )


    return db.query(
        query.exists()
    ).scalar()


def validate_leave_dates(
    start_date: date,
    end_date: date
):

    if end_date < start_date:

        raise ValueError(
            "End date cannot be before start date"
        )


    if start_date < date.today():

        raise ValueError(
            "Leave cannot be applied for past dates"
        )


    if calculate_weekdays(
        start_date,
        end_date
    ) == 0:

        raise ValueError(
            "Leave period must contain at least one weekday"
        )


def validate_balance(
    db: Session,
    employee_id: int,
    leave_type: str,
    start_date: date,
    total_days: int
):

    if (
        start_date.year
        != (
            start_date
            + timedelta(
                days=total_days - 1
            )
        ).year
    ):

        raise ValueError(
            "Leave requests spanning calendar years are not supported"
        )


    allocated = LEAVE_BALANCES[
        leave_type
    ]


    used = get_approved_usage(
        db,
        employee_id,
        leave_type,
        start_date.year
    )


    pending = (
        db.query(
            func.coalesce(
                func.sum(
                    LeaveRequest.total_days
                ),
                0
            )
        )
        .filter(
            LeaveRequest.employee_id
            == employee_id,

            LeaveRequest.leave_type
            == leave_type,

            LeaveRequest.status
            == "Pending",

            func.year(
                LeaveRequest.start_date
            )
            == start_date.year
        )
        .scalar()
    ) or 0


    if (
        used
        + int(pending)
        + total_days
        > allocated
    ):

        raise ValueError(
            f"Insufficient {leave_type} leave balance. "
            f"Allocated={allocated}, "
            f"approved_used={used}, "
            f"pending_reserved={int(pending)}, "
            f"requested={total_days}"
        )


def get_balance(
    db: Session,
    employee_id: int,
    year: int
):

    allocated = dict(
        LEAVE_BALANCES
    )


    approved_used = {
        leave_type:
            get_approved_usage(
                db,
                employee_id,
                leave_type,
                year
            )

        for leave_type
        in LEAVE_BALANCES
    }


    remaining = {

        leave_type:
            max(
                0,
                allocated[leave_type]
                - approved_used[leave_type]
            )

        for leave_type
        in LEAVE_BALANCES
    }


    return (
        allocated,
        approved_used,
        remaining
    )