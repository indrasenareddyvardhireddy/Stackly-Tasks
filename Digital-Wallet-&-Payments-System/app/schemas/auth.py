import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import Role
from app.schemas.common import Phone


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    phone: Phone
    password: str = Field(min_length=8, max_length=72)
    role: Role = Role.USER
    business_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    business_category: Optional[str] = Field(default=None, min_length=2, max_length=80)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v):
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Password must contain at least one letter and one digit")
        return v

    @model_validator(mode="after")
    def merchant_fields(self):
        if self.role == Role.MERCHANT and not (self.business_name and self.business_category):
            raise ValueError("business_name and business_category are required for merchants")
        return self


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
