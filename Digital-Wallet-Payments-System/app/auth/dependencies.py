from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_token
from app.database import get_db
from app.models import Role, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(status_code=401, detail="Invalid or expired token",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    payload = decode_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise unauthorized
    try:
        user = db.query(User).filter(User.id == int(payload["sub"])).first()
    except ValueError:
        raise unauthorized
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    return user


def require_roles(*roles: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission to access this resource")
        return user
    return checker


require_admin = require_roles(Role.ADMIN)
require_user = require_roles(Role.USER)
require_merchant = require_roles(Role.MERCHANT)
require_user_or_merchant = require_roles(Role.USER, Role.MERCHANT)
