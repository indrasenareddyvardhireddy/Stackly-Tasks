from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.users import User
from app.models.member import Member
from app.schemas.users import UserRegister
from app.auth.jwt import (
    hash_password,
    verify_password,
    create_access_token
)


def register_user(
    db: Session,
    data: UserRegister
):

    # Check username
    existing_user = db.query(User).filter(
        User.username == data.username
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username already exists"
        )

    # Check user email
    existing_user_email = db.query(User).filter(
        User.email == data.email
    ).first()

    if existing_user_email:
        raise HTTPException(
            status_code=409,
            detail="User email already exists"
        )

    # Validate role
    role = data.role.capitalize()

    if role not in ["Admin", "User"]:
        raise HTTPException(
            status_code=400,
            detail="Role must be Admin or User"
        )

    # Check member email
    existing_member = db.query(Member).filter(
        Member.email == data.email
    ).first()

    if existing_member:
        raise HTTPException(
            status_code=409,
            detail="Member email already exists"
        )

    # Create User
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role=role,
        is_active=True
    )

    db.add(user)

    # Generate user_id before creating Member
    db.flush()

    # Automatically create Member
    member = Member(
        user_id=user.user_id,
        name=data.username,
        email=data.email,
        phone=data.phone,
        address=data.address,
        membership_date=date.today(),
        is_active=True
    )

    db.add(member)

    try:
        db.commit()

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to create user and member"
        )

    db.refresh(user)

    return user


def login_user(
    db: Session,
    username: str,
    password: str
):

    user = db.query(User).filter(
        User.username == username
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(
        password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive"
        )

    token = create_access_token(
        user.username,
        user.role
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }