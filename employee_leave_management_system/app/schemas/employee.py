from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=150)
    phone: str
    department_id: int = Field(gt=0)
    designation: str = Field(min_length=2, max_length=100)
    salary: Decimal = Field(gt=0)
    date_of_joining: date
    employment_type: str = Field(
        pattern=r"^(Full-Time|Part-Time|Intern|Contract)$"
    )
    is_active: bool = True

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        if len(value) != 10:
            raise ValueError("Phone number must contain exactly 10 digits")

        if not value.isdigit():
            raise ValueError("Phone number must contain digits only")

        if value[0] not in "6789":
            raise ValueError(
                "Phone number must start with 6, 7, 8, or 9"
            )

        return value


class EmployeeUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150
    )

    phone: str | None = None

    department_id: int | None = Field(
        default=None,
        gt=0
    )

    designation: str | None = Field(
        default=None,
        min_length=2,
        max_length=100
    )

    salary: Decimal | None = Field(
        default=None,
        gt=0
    )

    is_active: bool | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value

        if len(value) != 10:
            raise ValueError("Phone number must contain exactly 10 digits")

        if not value.isdigit():
            raise ValueError("Phone number must contain digits only")

        if value[0] not in "6789":
            raise ValueError(
                "Phone number must start with 6, 7, 8, or 9"
            )

        return value


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: int
    user_id: int
    employee_code: str
    name: str
    email: str
    phone: str
    department_id: int
    designation: str
    salary: Decimal
    date_of_joining: date
    employment_type: str
    is_active: bool


class EmployeeCreateResponse(BaseModel):
    employee_id: int
    user_id: int
    employee_code: str
    name: str
    email: str
    username: str
    temporary_password: str
    role: str


class EmployeePasswordResetResponse(BaseModel):
    employee_id: int
    user_id: int
    username: str
    temporary_password: str
    message: str