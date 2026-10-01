from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    Query
)

from sqlalchemy import (
    extract,
    func
)

from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.database import get_db

from app.models.department import Department
from app.models.employee import Employee
from app.models.leave_request import LeaveRequest
from app.models.user import User

from app.schemas.report import (
    DashboardResponse,
    DepartmentEmployeeCount,
    LeaveSummaryItem,
    LeaveSummaryResponse
)


router = APIRouter(
    tags=["Reports"]
)


@router.get(
    "/dashboard",
    response_model=DashboardResponse
)
def dashboard(
    db: Session = Depends(get_db),

    _: User = Depends(
        require_roles(
            "Admin",
            "HR"
        )
    )
):

    total = (
        db.query(Employee)
        .count()
    )


    active = (
        db.query(Employee)
        .filter(
            Employee.is_active.is_(True)
        )
        .count()
    )


    rows = (
        db.query(
            Department.department_id,
            Department.department_name,
            func.count(
                Employee.employee_id
            )
        )
        .outerjoin(
            Employee,
            Employee.department_id
            == Department.department_id
        )
        .group_by(
            Department.department_id,
            Department.department_name
        )
        .all()
    )


    today = date.today()


    employees_on_leave = (
        db.query(
            LeaveRequest.employee_id
        )
        .filter(
            LeaveRequest.status
            == "Approved",

            LeaveRequest.start_date
            <= today,

            LeaveRequest.end_date
            >= today
        )
        .distinct()
        .count()
    )


    pending = (
        db.query(LeaveRequest)
        .filter(
            LeaveRequest.status
            == "Pending"
        )
        .count()
    )


    return DashboardResponse(

        total_employees=total,

        active_employees=active,

        employees_per_department=[
            DepartmentEmployeeCount(
                department_id=row[0],
                department_name=row[1],
                employee_count=row[2]
            )

            for row in rows
        ],

        pending_leave_requests=pending,

        employees_on_leave_today=
            employees_on_leave
    )


@router.get(
    "/leave-summary",
    response_model=LeaveSummaryResponse
)
def leave_summary(

    year: int = Query(
        ...,
        ge=2000,
        le=2100
    ),

    month: int = Query(
        ...,
        ge=1,
        le=12
    ),

    db: Session = Depends(get_db),

    _: User = Depends(
        require_roles(
            "Admin",
            "HR"
        )
    )
):

    rows = (
        db.query(
            LeaveRequest.leave_type,
            LeaveRequest.status,
            func.count(
                LeaveRequest.leave_id
            )
        )
        .filter(
            extract(
                "year",
                LeaveRequest.start_date
            ) == year,

            extract(
                "month",
                LeaveRequest.start_date
            ) == month
        )
        .group_by(
            LeaveRequest.leave_type,
            LeaveRequest.status
        )
        .all()
    )


    return LeaveSummaryResponse(

        year=year,

        month=month,

        summary=[
            LeaveSummaryItem(
                leave_type=row[0],
                status=row[1],
                count=row[2]
            )

            for row in rows
        ]
    )