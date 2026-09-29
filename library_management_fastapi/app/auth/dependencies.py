import os

from fastapi import (
    Depends,
    HTTPException,
    status
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from jose import JWTError, jwt

from sqlalchemy.orm import Session

from dotenv import load_dotenv

from app.database import get_db
from app.models.users import User
from app.models.member import Member


load_dotenv()


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "library-management-secret-key"
)

ALGORITHM = os.getenv(
    "ALGORITHM",
    "HS256"
)


security = HTTPBearer()


# =========================================================
# GET CURRENT USER
# =========================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):

    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={
            "WWW-Authenticate": "Bearer"
        }
    )

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")

        if username is None:
            raise credentials_exception

    except JWTError:

        raise credentials_exception


    user = db.query(User).filter(
        User.username == username
    ).first()


    if user is None:

        raise credentials_exception


    if not user.is_active:

        raise HTTPException(
            status_code=403,
            detail="User account is inactive"
        )


    return user


# =========================================================
# GET CURRENT ADMIN
# =========================================================

def get_current_admin(
    current_user: User = Depends(get_current_user)
):

    if current_user.role.lower() != "admin":

        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user


# =========================================================
# GET CURRENT MEMBER
# =========================================================

def get_current_member(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    member = db.query(Member).filter(
        Member.user_id == current_user.user_id
    ).first()


    if member is None:

        raise HTTPException(
            status_code=404,
            detail="Member profile not found"
        )


    return member


# =========================================================
# MEMBER ACCESS
# =========================================================
#
# Admin:
#   Can view any member.
#
# User:
#   Can view only their own member record.
#
# =========================================================

def get_member_access(
    member_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    member = db.query(Member).filter(
        Member.member_id == member_id
    ).first()


    if member is None:

        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )


    # Admin can access any member
    if current_user.role.lower() == "admin":

        return member


    # Normal user can access only their own member
    if member.user_id != current_user.user_id:

        raise HTTPException(
            status_code=403,
            detail="You can only view your own borrowing information"
        )


    return member