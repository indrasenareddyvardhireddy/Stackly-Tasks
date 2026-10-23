from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import (ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET_KEY, get_db)
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)

ADMIN, OWNER, PARTNER, CUSTOMER = "admin", "restaurant_owner", "delivery_partner", "customer"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def user_from_token(token: str, db: Session) -> Optional[User]:
    """Returns the active user for a token, or None when invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    return user if user and user.is_active else None


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    user = user_from_token(creds.credentials, db)
    if user is None:
        raise unauthorized
    return user


def require_roles(*roles: str, approved: bool = False):
    """Dependency factory: 403 if role not allowed; 403 if approval needed but missing."""
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to access this resource")
        if approved and user.role in (OWNER, PARTNER) and not user.is_approved:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your account is awaiting admin approval")
        return user
    return dep
