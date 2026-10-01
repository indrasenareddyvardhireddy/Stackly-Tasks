from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status
)

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password
)

from app.database import get_db

from app.models.user import User

from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse
)


router = APIRouter(
    tags=["Authentication"]
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db)
):

    existing = (
        db.query(User)
        .filter(
            or_(
                User.username == payload.username,
                User.email == payload.email
            )
        )
        .first()
    )

    if existing:

        raise HTTPException(
            status_code=409,
            detail="Username or email already exists"
        )


    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(
            payload.password
        ),
        role=payload.role,
        is_active=True
    )


    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):

    user = (
        db.query(User)
        .filter(
            User.username == payload.username
        )
        .first()
    )


    if (
        not user
        or not verify_password(
            payload.password,
            user.password_hash
        )
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )


    if not user.is_active:

        raise HTTPException(
            status_code=401,
            detail="Inactive users cannot log in"
        )


    token = create_access_token(
        {
            "sub": str(user.user_id),
            "role": user.role
        }
    )


    return TokenResponse(
        access_token=token
    )


@router.get(
    "/me",
    response_model=UserResponse
)
def me(
    current_user: User = Depends(
        get_current_user
    )
):

    return current_user