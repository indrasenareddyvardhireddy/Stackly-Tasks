from datetime import timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext

from app.config import settings
from app.utils.common import utcnow

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_secret(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_secret(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(user_id: int, role: str) -> str:
    now = utcnow()
    payload = {"sub": str(user_id), "role": role, "iat": now,
               "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
