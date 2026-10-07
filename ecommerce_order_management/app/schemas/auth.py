from pydantic import BaseModel, EmailStr, Field


# =========================================================
# REGISTER
# =========================================================

class RegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=100
    )

    email: EmailStr

    password: str = Field(
        ...,
        min_length=8,
        max_length=72
    )


# =========================================================
# LOGIN
# =========================================================

class LoginRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        ...,
        min_length=1,
        max_length=72
    )


# =========================================================
# JWT RESPONSE
# =========================================================

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# =========================================================
# USER RESPONSE
# =========================================================

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# =========================================================
# FORGOT PASSWORD
# =========================================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


# =========================================================
# RESET PASSWORD
# =========================================================

class ResetPasswordRequest(BaseModel):
    token: str

    new_password: str = Field(
        ...,
        min_length=8,
        max_length=72
    )


# =========================================================
# CHANGE PASSWORD
# =========================================================

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        ...,
        min_length=1,
        max_length=72
    )

    new_password: str = Field(
        ...,
        min_length=8,
        max_length=72
    )