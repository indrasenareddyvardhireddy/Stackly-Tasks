from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_roles
from app.auth.security import create_access_token, hash_password, verify_password
from app.config import settings
from app.database import get_db
from app.models import User
from app.models.enums import Role
from app.schemas.user import RegisterRequest, Token, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


async def create_user(db: AsyncSession, data: RegisterRequest, role: Role) -> User:
    email = data.email.lower()
    exists = await db.execute(select(User.id).where(User.email == email))
    if exists.first():
        raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(name=data.name, email=email, hashed_password=hash_password(data.password), role=role, is_active=True)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered")
    return user


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Public registration. Always creates a Customer account."""
    return await create_user(db, data, Role.CUSTOMER)


@router.post("/admins", response_model=UserOut, status_code=201, summary="Create an Admin account (Admin only)")
async def create_admin(
    data: RegisterRequest, db: AsyncSession = Depends(get_db), _: User = Depends(require_roles(Role.ADMIN))
):
    return await create_user(db, data, Role.ADMIN)


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """`username` is the account email (OAuth2 form so Swagger's Authorize button works)."""
    res = await db.execute(select(User).where(User.email == form.username.strip().lower()))
    user = res.scalar_one_or_none()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"}
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    return Token(access_token=create_access_token(user), expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
