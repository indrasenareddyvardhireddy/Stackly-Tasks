from datetime import datetime, timedelta, timezone
import secrets
import hashlib
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.database import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def generate_reset_token() -> str:
    return secrets.token_urlsafe(48)

def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
