from datetime import datetime, timedelta
import hashlib

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, RefreshToken
from app.schemas import RegisterIn, LoginIn, UserOut
from app.auth.security import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
)
from app.auth.dependencies import get_current_user
from app.config import settings
from app.services.notifications import send_registration_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(
    data: RegisterIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Register a Patient and queue a registration confirmation email."""
    existing_user = db.scalar(select(User.id).where(User.email == data.email))
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        name=data.name,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role="patient",
    )

    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    # Queue email only after the user has been committed successfully.
    background_tasks.add_task(
        send_registration_email,
        user.name,
        user.email,
    )

    return user


@router.post("/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is inactive")

    access = create_token(
        str(user.id), "access", timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    )
    refresh = create_token(
        str(user.id), "refresh", timedelta(days=settings.REFRESH_TOKEN_DAYS)
    )
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hashlib.sha256(refresh.encode()).hexdigest(),
            expires_at=datetime.utcnow()
            + timedelta(days=settings.REFRESH_TOKEN_DAYS),
        )
    )
    db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": UserOut.model_validate(user),
    }


@router.post("/refresh")
def refresh_token(data: dict, db: Session = Depends(get_db)):
    token = data.get("refresh_token", "")
    try:
        payload = decode_token(token, "refresh")
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    digest = hashlib.sha256(token.encode()).hexdigest()
    stored = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == digest,
            RefreshToken.user_id == uid,
        )
    )
    if not stored or stored.revoked or stored.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token revoked or expired")

    user = db.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")

    return {
        "access_token": create_token(
            str(uid), "access", timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
        ),
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    data: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    token = data.get("refresh_token", "")
    digest = hashlib.sha256(token.encode()).hexdigest()
    stored = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == digest,
            RefreshToken.user_id == user.id,
        )
    )
    if stored:
        stored.revoked = True
        db.commit()
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
