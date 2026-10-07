from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.cart import Cart
from app.models.password_reset import PasswordResetToken

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
)

from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_reset_token,
    hash_reset_token,
)

from app.utils.email import send_email
from app.auth.dependencies import get_current_user


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# =========================================================
# REGISTER CUSTOMER
# =========================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201
)
def register(
    data: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Check duplicate email
    existing_email = db.scalar(
        select(User).where(User.email == data.email)
    )

    if existing_email:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    # Check duplicate username
    existing_username = db.scalar(
        select(User).where(User.username == data.username)
    )

    if existing_username:
        raise HTTPException(
            status_code=409,
            detail="Username already exists"
        )

    # Public registration is ALWAYS Customer.
    # Users cannot register themselves as Admin.
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role=UserRole.Customer,
        is_active=True
    )

    db.add(user)
    db.flush()

    # Every customer gets one cart
    cart = Cart(
        customer_id=user.id
    )

    db.add(cart)

    db.commit()
    db.refresh(user)

    # Send registration email in background
    background_tasks.add_task(
        send_email,
        user.email,
        "Welcome to E-Commerce",
        (
            f"Hello {user.username},\n\n"
            "Your customer account has been created successfully.\n\n"
            "Thank you for registering with our E-Commerce platform."
        )
    )

    return user


# =========================================================
# LOGIN
# =========================================================

@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    # Login using email
    user = db.scalar(
        select(User).where(User.email == data.email)
    )

    # Invalid email/password
    if not user or not verify_password(
        data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    # Inactive account
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive"
        )

    # Create JWT token
    access_token = create_access_token(
        {
            "sub": str(user.id),
            "role": user.role.value
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# =========================================================
# CURRENT USER
# =========================================================

@router.get(
    "/me",
    response_model=UserResponse
)
def me(
    user=Depends(get_current_user)
):
    return user


# =========================================================
# FORGOT PASSWORD
# =========================================================

@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = db.scalar(
        select(User).where(User.email == data.email)
    )

    # Always return the same message.
    # This prevents account enumeration.
    if user:

        # Invalidate previous unused reset tokens
        old_tokens = db.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None)
            )
        ).all()

        for old_token in old_tokens:
            old_token.used_at = datetime.utcnow()

        # Generate new reset token
        raw_token = generate_reset_token()

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )

        db.add(reset_token)
        db.commit()

        # Password reset link
        reset_link = (
            f"http://127.0.0.1:8000/reset-password"
            f"?token={raw_token}"
        )

        # Send email in background
        background_tasks.add_task(
            send_email,
            user.email,
            "Password Reset Request",
            (
                f"Hello {user.username},\n\n"
                "We received a request to reset your password.\n\n"
                f"Use the following link within 15 minutes:\n"
                f"{reset_link}\n\n"
                "If you did not request this password reset, "
                "please ignore this email."
            )
        )

    return {
        "message": (
            "If an account exists for that email, "
            "a password reset email has been sent."
        )
    }


# =========================================================
# RESET PASSWORD
# =========================================================

@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    # Find token using hashed token
    reset = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash
            == hash_reset_token(data.token)
        )
    )

    if not reset:
        raise HTTPException(
            status_code=400,
            detail="Invalid password reset token"
        )

    # Prevent token reuse
    if reset.used_at is not None:
        raise HTTPException(
            status_code=400,
            detail="Password reset token has already been used"
        )

    # Check token expiry
    if reset.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="Password reset token has expired"
        )

    # Find user
    user = db.get(
        User,
        reset.user_id
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Invalid password reset request"
        )

    # Update password
    user.password_hash = hash_password(
        data.new_password
    )

    # Mark reset token as used
    reset.used_at = datetime.utcnow()

    db.commit()

    return {
        "message": (
            "Password reset successful. "
            "You can now login with your new password."
        )
    }


# =========================================================
# CHANGE PASSWORD
# =========================================================

@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    # Verify current password
    if not verify_password(
        data.current_password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    # Prevent same password
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from current password"
        )

    # Update password
    user.password_hash = hash_password(
        data.new_password
    )

    db.commit()

    return {
        "message": "Password changed successfully"
    }