from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.users import (
    UserRegister,
    UserLogin,
    UserResponse,
    Token
)

from app.services.auth_service import (
    register_user,
    login_user
)

from app.auth.dependencies import get_current_user


router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201
)
def register(
    data: UserRegister,
    db: Session = Depends(get_db)
):

    return register_user(
        db,
        data
    )


@router.post(
    "/login",
    response_model=Token
)
def login(
    data: UserLogin,
    db: Session = Depends(get_db)
):

    return login_user(
        db,
        data.username,
        data.password
    )


@router.get(
    "/me",
    response_model=UserResponse
)
def me(
    current_user=Depends(get_current_user)
):

    return current_user