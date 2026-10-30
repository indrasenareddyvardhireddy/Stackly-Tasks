from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database import get_db
from app.models.enums import Role
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def authenticate_token(token: str, db: Session) -> Optional[User]:
    """Returns the active user for a valid token, otherwise None (used by REST and WebSockets)."""
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        return None
    return user


def _unauthorized():
    return HTTPException(status_code=401, detail="Invalid or expired token",
                         headers={"WWW-Authenticate": "Bearer"})


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
                     db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    user = authenticate_token(creds.credentials, db)
    if user is None:
        raise _unauthorized()
    return user


def get_optional_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
                      db: Session = Depends(get_db)) -> Optional[User]:
    """Anonymous access allowed; a token that is present but invalid is still a 401."""
    if creds is None:
        return None
    user = authenticate_token(creds.credentials, db)
    if user is None:
        raise _unauthorized()
    return user


def require_roles(*roles: Role):
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(sorted(allowed))}")
        return user

    return checker


def get_approved_organizer(user: User = Depends(require_roles(Role.ORGANIZER))) -> User:
    if not user.is_approved:
        raise HTTPException(status_code=403, detail="Organizer account is not approved by Admin yet")
    return user
