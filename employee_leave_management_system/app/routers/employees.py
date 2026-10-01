from __future__ import annotations

import secrets
import string
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.auth.security import hash_password
from app.database import get_db
from app.models.department import Department
from app.models.employee import Employee
from app.models.user import User
from app.schemas.employee import EmployeePasswordResetResponse
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeCreateResponse,
    EmployeeResponse,
    EmployeeUpdate,
)


router = APIRouter(
    prefix="/employees",
    tags=["Employees"]
)


def generate_temporary_password(length: int = 10) -> str:
    characters = string.ascii_letters + string.digits

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


def ensure_unique_employee(
    db: Session,
    employee_code: str,
    email: str,
):
    existing_code = (
        db.query(Employee)
        .filter(
            Employee.employee_code == employee_code
        )
        .first()
    )

    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee code already exists"
        )

    existing_email = (
        db.query(Employee)
        .filter(
            func.lower(Employee.email)
            == email.lower()
        )
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee email already exists"
        )


@router.post(
    "",
    response_model=EmployeeCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "HR")
    ),
):

    if payload.date_of_joining > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Joining date cannot be in the future"
        )

    department = (
        db.query(Department)
        .filter(
            Department.department_id
            == payload.department_id
        )
        .first()
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    ensure_unique_employee(
        db,
        payload.employee_code,
        payload.email
    )

    username = payload.name.strip()

    existing_username = (
        db.query(User)
        .filter(
            func.lower(User.username)
            == username.lower()
        )
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this employee name already exists"
        )

    existing_user_email = (
        db.query(User)
        .filter(
            func.lower(User.email)
            == payload.email.lower()
        )
        .first()
    )

    if existing_user_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists"
        )

    temporary_password = generate_temporary_password()

    user = User(
        username=username,
        email=payload.email,
        password_hash=hash_password(
            temporary_password
        ),
        role="Employee",
        is_active=payload.is_active,
    )

    db.add(user)
    db.flush()

    employee = Employee(
        user_id=user.user_id,
        employee_code=payload.employee_code,
        name=username,
        email=payload.email,
        phone=payload.phone,
        department_id=payload.department_id,
        designation=payload.designation,
        salary=payload.salary,
        date_of_joining=payload.date_of_joining,
        employment_type=payload.employment_type,
        is_active=payload.is_active,
    )

    db.add(employee)
    db.commit()

    db.refresh(employee)
    db.refresh(user)

    return EmployeeCreateResponse(
        employee_id=employee.employee_id,
        user_id=user.user_id,
        employee_code=employee.employee_code,
        name=employee.name,
        email=employee.email,
        username=user.username,
        temporary_password=temporary_password,
        role=user.role,
    )


@router.get(
    "",
    response_model=list[EmployeeResponse]
)
def list_employees(
    skip: int = Query(
        0,
        ge=0
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100
    ),
    department_id: int | None = Query(
        None,
        gt=0
    ),
    employment_type: str | None = None,
    is_active: bool | None = None,
    sort_by: str = Query(
        "employee_id"
    ),
    sort_order: str = Query(
        "asc"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = db.query(Employee)

    if current_user.role == "Employee":

        employee = (
            query
            .filter(
                Employee.user_id
                == current_user.user_id
            )
            .first()
        )

        if not employee:
            return []

        query = query.filter(
            Employee.employee_id
            == employee.employee_id
        )

    if department_id:
        query = query.filter(
            Employee.department_id
            == department_id
        )

    if employment_type:
        query = query.filter(
            Employee.employment_type
            == employment_type
        )

    if is_active is not None:
        query = query.filter(
            Employee.is_active
            == is_active
        )

    allowed_sort_fields = {
        "employee_id": Employee.employee_id,
        "name": Employee.name,
        "salary": Employee.salary,
        "date_of_joining": Employee.date_of_joining,
        "created_at": Employee.created_at,
    }

    sort_column = allowed_sort_fields.get(
        sort_by,
        Employee.employee_id
    )

    if sort_order.lower() == "desc":
        query = query.order_by(
            sort_column.desc()
        )
    else:
        query = query.order_by(
            sort_column.asc()
        )

    return (
        query
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse
)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    employee = (
        db.query(Employee)
        .filter(
            Employee.employee_id
            == employee_id
        )
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )

    if current_user.role == "Employee":

        if employee.user_id != current_user.user_id:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own employee profile"
            )

    return employee


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse
)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    employee = (
        db.query(Employee)
        .filter(Employee.employee_id == employee_id)
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )

    # ---------------------------------------------------------
    # ADMIN / HR
    # Can update any employee
    # ---------------------------------------------------------

    if current_user.role in ["Admin", "HR"]:
        data = payload.model_dump(exclude_unset=True)

        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update"
            )

        # If name is being changed, keep username synchronized
        if "name" in data:
            new_name = data["name"].strip()

            existing_user = (
                db.query(User)
                .filter(
                    func.lower(User.username) == new_name.lower(),
                    User.user_id != employee.user_id
                )
                .first()
            )

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists"
                )

            employee.user.username = new_name

        for field, value in data.items():
            setattr(employee, field, value)

        db.commit()
        db.refresh(employee)

        return employee

    # ---------------------------------------------------------
    # EMPLOYEE
    # Can update only their own employee record
    # ---------------------------------------------------------

    if current_user.role == "Employee":

        if employee.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can update only your own employee details"
            )

        data = payload.model_dump(exclude_unset=True)

        # Employee can update only name and phone
        allowed_fields = {"name", "phone"}

        invalid_fields = set(data.keys()) - allowed_fields

        if invalid_fields:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Employees can update only name and phone"
                )
            )

        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update"
            )

        # Keep username synchronized with employee name
        if "name" in data:
            new_name = data["name"].strip()

            existing_user = (
                db.query(User)
                .filter(
                    func.lower(User.username) == new_name.lower(),
                    User.user_id != employee.user_id
                )
                .first()
            )

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists"
                )

            employee.user.username = new_name

        for field, value in data.items():
            setattr(employee, field, value)

        db.commit()
        db.refresh(employee)

        return employee

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions"
    )


@router.delete(
    "/{employee_id}",
    status_code=status.HTTP_200_OK
)
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "HR")
    ),
):

    employee = (
        db.query(Employee)
        .filter(
            Employee.employee_id
            == employee_id
        )
        .first()
    )

    if not employee:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )

    employee.is_active = False

    # Deactivate employee login account
    if employee.user:
        employee.user.is_active = False

    db.commit()

    return {
        "message": "Employee deactivated successfully"
    }


def get_employee_for_user(
    db: Session,
    current_user: User
) -> Employee:

    employee = (
        db.query(Employee)
        .filter(
            Employee.user_id
            == current_user.user_id
        )
        .first()
    )

    if not employee:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found"
        )

    return employee

@router.post(
    "/{employee_id}/reset-password",
    response_model=EmployeePasswordResetResponse,
    status_code=status.HTTP_200_OK
)
def reset_employee_password(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "HR"))
):
    # ---------------------------------------------------------
    # Find employee
    # ---------------------------------------------------------

    employee = (
        db.query(Employee)
        .filter(Employee.employee_id == employee_id)
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )

    # ---------------------------------------------------------
    # Find linked user
    # ---------------------------------------------------------

    user = (
        db.query(User)
        .filter(User.user_id == employee.user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Login account for this employee was not found"
        )

    # ---------------------------------------------------------
    # Generate new temporary password
    # ---------------------------------------------------------

    characters = (
        string.ascii_letters
        + string.digits
        + "!@#$%"
    )

    temporary_password = "".join(
        secrets.choice(characters)
        for _ in range(12)
    )

    # ---------------------------------------------------------
    # Hash and save password
    # ---------------------------------------------------------

    user.password_hash = hash_password(temporary_password)

    # Make sure the account is active
    user.is_active = True

    db.commit()
    db.refresh(user)

    # ---------------------------------------------------------
    # Return temporary password
    # ---------------------------------------------------------

    return EmployeePasswordResetResponse(
        employee_id=employee.employee_id,
        user_id=user.user_id,
        username=user.username,
        temporary_password=temporary_password,
        message="Employee password reset successfully"
    )