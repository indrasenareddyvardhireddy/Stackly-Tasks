from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role
from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(pattern=r"^\d{10}$", description="10 digit phone number")
    password: str = Field(min_length=8, max_length=72)
    role: Role = Role.CUSTOMER   # only Customer / Organizer are accepted publicly


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class StaffCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(pattern=r"^\d{10}$")
    password: str = Field(min_length=8, max_length=72)
    venue_id: int


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    phone: str
    role: str
    is_active: bool
    is_approved: bool
    venue_id: Optional[int] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
