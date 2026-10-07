from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.config import settings


# =========================================================
# HTTP BEARER AUTHENTICATION
# =========================================================
#
# Swagger will now show:
#
# HTTPBearer
# Value: Bearer <JWT_TOKEN>
#
# instead of OAuth2 username/password.
#

security = HTTPBearer()


# =========================================================
# GET CURRENT USER
# =========================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )

        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.scalar(
        select(User).where(User.id == user_id)
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


# =========================================================
# ROLE CHECKING
# =========================================================

def require_role(*allowed_roles: str) -> Callable:
    """
    Allows one or more roles.

    Examples:

        Depends(require_role("Admin"))

        Depends(require_role("Customer"))

        Depends(require_role("Admin", "Customer"))
    """

    def role_checker(
        current_user: User = Depends(get_current_user)
    ):
        current_role = current_user.role

        # SQLAlchemy Enum can return an enum object.
        if isinstance(current_role, UserRole):
            current_role = current_role.value

        if current_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        return current_user

    return role_checker


# =========================================================
# ADMIN ONLY
# =========================================================

def require_admin(
    current_user: User = Depends(get_current_user)
):
    current_role = current_user.role

    if isinstance(current_role, UserRole):
        current_role = current_role.value

    if current_role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user


# =========================================================
# CUSTOMER ONLY
# =========================================================

def require_customer(
    current_user: User = Depends(get_current_user)
):
    current_role = current_user.role

    if isinstance(current_role, UserRole):
        current_role = current_role.value

    if current_role != "Customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer access required"
        )

    return current_user