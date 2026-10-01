from __future__ import annotations

from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query
)

from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    require_roles
)

from app.database import get_db

from app.models.employee import Employee
from app.models.leave_request import LeaveRequest
from app.models.user import User

from app.schemas.leave import (
    LeaveBalanceResponse,
    LeaveCreate,
    LeaveReject,
    LeaveResponse
)

from app.services.leave_service import (
    calculate_weekdays,
    get_balance,
    has_overlap,
    validate_balance,
    validate_leave_dates
)


# No prefix here
router = APIRouter(
    tags=["Leaves"]
)


# Prefix is added in main.py:
# /employees
employees_leave_router = APIRouter(
    tags=["Employees - Leaves"]
)


def get_employee_for_user(
    db: Session,
    user: User
) -> Employee:

    employee = (
        db.query(Employee)
        .filter(
            Employee.email.ilike(
                user.email
            )
        )
        .first()
    )


    if not employee:

        raise HTTPException(
            status_code=404,
            detail=(
                "No employee profile is "
                "linked to the current user"
            )
        )


    return employee


@router.post(
    "",
    response_model=LeaveResponse,
    status_code=201
)
def create_leave(
    payload: LeaveCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    if current_user.role == "Employee":

        own_employee = get_employee_for_user(
            db,
            current_user
        )


        if (
            payload.employee_id
            != own_employee.employee_id
        ):

            raise HTTPException(
                status_code=403,
                detail=(
                    "Employees can apply "
                    "only for themselves"
                )
            )


    elif current_user.role not in {
        "Admin",
        "HR"
    }:

        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )


    employee = db.get(
        Employee,
        payload.employee_id
    )


    if not employee:

        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )


    if not employee.is_active:

        raise HTTPException(
            status_code=400,
            detail=(
                "Inactive employees "
                "cannot apply for leave"
            )
        )


    try:

        validate_leave_dates(
            payload.start_date,
            payload.end_date
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


    total_days = calculate_weekdays(
        payload.start_date,
        payload.end_date
    )


    if has_overlap(
        db,
        employee.employee_id,
        payload.start_date,
        payload.end_date
    ):

        raise HTTPException(
            status_code=409,
            detail=(
                "Overlapping pending or "
                "approved leave already exists"
            )
        )


    try:

        validate_balance(
            db,
            employee.employee_id,
            payload.leave_type,
            payload.start_date,
            total_days
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


    leave = LeaveRequest(

        employee_id=
            employee.employee_id,

        leave_type=
            payload.leave_type,

        start_date=
            payload.start_date,

        end_date=
            payload.end_date,

        total_days=
            total_days,

        reason=
            payload.reason,

        status="Pending"
    )


    db.add(leave)
    db.commit()
    db.refresh(leave)

    return leave


@router.get(
    "",
    response_model=list[LeaveResponse]
)
def list_leaves(

    status_filter: str | None = Query(
        None,
        alias="status",
        pattern=r"^(Pending|Approved|Rejected|Cancelled)$"
    ),

    leave_type: str | None = Query(
        None,
        pattern=r"^(Sick|Casual|Earned)$"
    ),

    employee_id: int | None = Query(
        None,
        gt=0
    ),

    from_date: date | None = None,

    to_date: date | None = None,

    skip: int = Query(
        0,
        ge=0
    ),

    limit: int = Query(
        10,
        ge=1,
        le=100
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    query = db.query(
        LeaveRequest
    )


    if current_user.role == "Employee":

        employee = get_employee_for_user(
            db,
            current_user
        )

        query = query.filter(
            LeaveRequest.employee_id
            == employee.employee_id
        )


    elif current_user.role not in {
        "Admin",
        "HR"
    }:

        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )


    if status_filter:

        query = query.filter(
            LeaveRequest.status
            == status_filter
        )


    if leave_type:

        query = query.filter(
            LeaveRequest.leave_type
            == leave_type
        )


    if employee_id:

        query = query.filter(
            LeaveRequest.employee_id
            == employee_id
        )


    if from_date:

        query = query.filter(
            LeaveRequest.end_date
            >= from_date
        )


    if to_date:

        query = query.filter(
            LeaveRequest.start_date
            <= to_date
        )


    return (
        query
        .order_by(
            LeaveRequest.start_date.desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get(
    "/{leave_id}",
    response_model=LeaveResponse
)
def get_leave(
    leave_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    leave = db.get(
        LeaveRequest,
        leave_id
    )


    if not leave:

        raise HTTPException(
            status_code=404,
            detail="Leave request not found"
        )


    if current_user.role == "Employee":

        employee = get_employee_for_user(
            db,
            current_user
        )


        if (
            leave.employee_id
            != employee.employee_id
        ):

            raise HTTPException(
                status_code=403,
                detail=(
                    "You can view only "
                    "your own leave requests"
                )
            )


    elif current_user.role not in {
        "Admin",
        "HR"
    }:

        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )


    return leave


@employees_leave_router.get(
    "/{employee_id}/leaves",
    response_model=list[LeaveResponse]
)
def employee_leaves(
    employee_id: int,

    skip: int = Query(
        0,
        ge=0
    ),

    limit: int = Query(
        10,
        ge=1,
        le=100
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    employee = db.get(
        Employee,
        employee_id
    )


    if not employee:

        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )


    if current_user.role == "Employee":

        own = get_employee_for_user(
            db,
            current_user
        )


        if (
            own.employee_id
            != employee_id
        ):

            raise HTTPException(
                status_code=403,
                detail=(
                    "Employees can view "
                    "only their own leaves"
                )
            )


    elif current_user.role not in {
        "Admin",
        "HR"
    }:

        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )


    return (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.employee_id
            == employee_id
        )
        .order_by(
            LeaveRequest.start_date.desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


@employees_leave_router.get(
    "/{employee_id}/leave-balance",
    response_model=LeaveBalanceResponse
)
def employee_leave_balance(
    employee_id: int,

    year: int = Query(
        default=date.today().year,
        ge=2000,
        le=2100
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    employee = db.get(
        Employee,
        employee_id
    )


    if not employee:

        raise HTTPException(
            status_code=404,
            detail="Employee not found"
        )


    if current_user.role == "Employee":

        own = get_employee_for_user(
            db,
            current_user
        )


        if (
            own.employee_id
            != employee_id
        ):

            raise HTTPException(
                status_code=403,
                detail=(
                    "Employees can view "
                    "only their own balance"
                )
            )


    elif current_user.role not in {
        "Admin",
        "HR"
    }:

        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )


    allocated, used, remaining = get_balance(
        db,
        employee_id,
        year
    )


    return LeaveBalanceResponse(

        employee_id=employee_id,

        year=year,

        allocated=allocated,

        approved_used=used,

        remaining=remaining
    )


@router.put(
    "/{leave_id}/approve",
    response_model=LeaveResponse
)
def approve_leave(
    leave_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_roles(
            "Admin",
            "HR"
        )
    )
):

    leave = db.get(
        LeaveRequest,
        leave_id
    )


    if not leave:

        raise HTTPException(
            status_code=404,
            detail="Leave request not found"
        )


    if leave.status != "Pending":

        raise HTTPException(
            status_code=400,
            detail=(
                "Only Pending leaves "
                "can be approved"
            )
        )


    employee = db.get(
        Employee,
        leave.employee_id
    )


    if (
        current_user.role == "HR"
        and employee
        and employee.email.lower()
        == current_user.email.lower()
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "HR cannot approve "
                "their own leave"
            )
        )


    try:

        validate_balance(
            db,
            leave.employee_id,
            leave.leave_type,
            leave.start_date,
            leave.total_days
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )


    leave.status = "Approved"

    leave.approved_by = (
        current_user.user_id
    )

    leave.rejection_reason = None


    db.commit()
    db.refresh(leave)

    return leave


@router.put(
    "/{leave_id}/reject",
    response_model=LeaveResponse
)
def reject_leave(
    leave_id: int,

    payload: LeaveReject,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_roles(
            "Admin",
            "HR"
        )
    )
):

    leave = db.get(
        LeaveRequest,
        leave_id
    )


    if not leave:

        raise HTTPException(
            status_code=404,
            detail="Leave request not found"
        )


    if leave.status != "Pending":

        raise HTTPException(
            status_code=400,
            detail=(
                "Only Pending leaves "
                "can be rejected"
            )
        )


    leave.status = "Rejected"

    leave.approved_by = (
        current_user.user_id
    )

    leave.rejection_reason = (
        payload.rejection_reason
    )


    db.commit()
    db.refresh(leave)

    return leave


@router.put(
    "/{leave_id}/cancel",
    response_model=LeaveResponse
)
def cancel_leave(
    leave_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    )
):

    leave = db.get(
        LeaveRequest,
        leave_id
    )


    if not leave:

        raise HTTPException(
            status_code=404,
            detail="Leave request not found"
        )


    if leave.status != "Pending":

        raise HTTPException(
            status_code=400,
            detail=(
                "Only Pending leaves "
                "can be cancelled"
            )
        )


    if current_user.role == "Employee":

        own = get_employee_for_user(
            db,
            current_user
        )


        if (
            leave.employee_id
            != own.employee_id
        ):

            raise HTTPException(
                status_code=403,
                detail=(
                    "Employees can cancel "
                    "only their own leaves"
                )
            )


    elif current_user.role not in {
        "Admin",
        "HR"
    }:

        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )


    leave.status = "Cancelled"

    db.commit()
    db.refresh(leave)

    return leave