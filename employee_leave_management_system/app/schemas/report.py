from pydantic import BaseModel


class DepartmentEmployeeCount(BaseModel):

    department_id: int
    department_name: str
    employee_count: int


class DashboardResponse(BaseModel):

    total_employees: int

    active_employees: int

    employees_per_department: list[
        DepartmentEmployeeCount
    ]

    pending_leave_requests: int

    employees_on_leave_today: int


class LeaveSummaryItem(BaseModel):

    leave_type: str
    status: str
    count: int


class LeaveSummaryResponse(BaseModel):

    year: int
    month: int

    summary: list[
        LeaveSummaryItem
    ]