from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field
)


class RegisterRequest(BaseModel):

    username: str = Field(
        min_length=3,
        max_length=100
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128
    )

    role: str = Field(
        default="Employee",
        pattern="^(Admin|HR|Employee)$"
    )


class LoginRequest(BaseModel):

    username: str = Field(
        min_length=1,
        max_length=100
    )

    password: str = Field(
        min_length=1,
        max_length=128
    )


class UserResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    user_id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):

    access_token: str

    token_type: str = "bearer"

    expires_in: int = 1800