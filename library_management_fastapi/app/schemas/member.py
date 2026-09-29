from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict, Field


class MemberCreate(BaseModel):

    username: str = Field(
        ...,
        min_length=3,
        max_length=100
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=6,
        max_length=100
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    phone: str = Field(
        ...,
        min_length=10,
        max_length=15
    )

    address: str = Field(
        ...,
        min_length=1,
        max_length=255
    )

    membership_date: Optional[date] = None

    is_active: bool = True


class MemberUpdate(BaseModel):

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100
    )

    email: Optional[EmailStr] = None

    phone: Optional[str] = Field(
        None,
        min_length=10,
        max_length=15
    )

    address: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255
    )

    is_active: Optional[bool] = None


class MemberResponse(BaseModel):

    member_id: int
    user_id: Optional[int]
    name: str
    email: EmailStr
    phone: str
    address: str
    membership_date: date
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )