from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles, get_current_user
from app.database import get_db
from app.models.department import Department
from app.models.employee import Employee
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
)


router = APIRouter(
    prefix="/departments",
    tags=["Departments"]
)


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED
)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin")
    ),
):

    existing_department = (
        db.query(Department)
        .filter(
            Department.department_name
            == payload.department_name
        )
        .first()
    )

    if existing_department:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department already exists"
        )

    department = Department(
        department_name=payload.department_name
    )

    db.add(department)
    db.commit()
    db.refresh(department)

    return department


@router.get(
    "",
    response_model=list[DepartmentResponse]
)
def get_departments(
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
    current_user: User = Depends(get_current_user),
):

    return (
        db.query(Department)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse
)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    department = (
        db.query(Department)
        .filter(
            Department.department_id
            == department_id
        )
        .first()
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    return department


@router.put(
    "/{department_id}",
    response_model=DepartmentResponse
)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin")
    ),
):

    department = (
        db.query(Department)
        .filter(
            Department.department_id
            == department_id
        )
        .first()
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    existing_department = (
        db.query(Department)
        .filter(
            Department.department_name
            == payload.department_name,
            Department.department_id
            != department_id
        )
        .first()
    )

    if existing_department:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department name already exists"
        )

    department.department_name = (
        payload.department_name
    )

    db.commit()
    db.refresh(department)

    return department


@router.delete(
    "/{department_id}"
)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin")
    ),
):

    department = (
        db.query(Department)
        .filter(
            Department.department_id
            == department_id
        )
        .first()
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    active_employees = (
        db.query(Employee)
        .filter(
            Employee.department_id
            == department_id,
            Employee.is_active == True
        )
        .count()
    )

    if active_employees > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot delete department because "
                "it has active employees"
            )
        )

    db.delete(department)
    db.commit()

    return {
        "message": "Department deleted successfully"
    }


@router.get(
    "/{department_id}/employees"
)
def get_department_employees(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    department = (
        db.query(Department)
        .filter(
            Department.department_id
            == department_id
        )
        .first()
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    employees = (
        db.query(Employee)
        .filter(
            Employee.department_id
            == department_id,
            Employee.is_active == True
        )
        .all()
    )

    return employees