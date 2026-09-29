from pydantic import BaseModel, EmailStr, ConfigDict


class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "User"

    phone: str
    address: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    user_id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )


class Token(BaseModel):
    access_token: str
    token_type: str