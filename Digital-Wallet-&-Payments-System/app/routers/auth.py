import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token, hash_secret, verify_secret
from app.config import settings
from app.database import get_db
from app.models import Account, AccountType, Merchant, Role, User, Wallet
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.utils.common import jsonable, utcnow
from app.utils.email import send_email

router = APIRouter(prefix="/auth", tags=["Auth"])


def user_dict(user: User) -> dict:
    d = {"id": user.id, "full_name": user.full_name, "email": user.email, "phone": user.phone, "role": user.role,
         "is_active": user.is_active, "created_at": user.created_at}
    if user.wallet:
        d["wallet_number"] = user.wallet.wallet_number
    if user.merchant:
        d["merchant"] = {"business_name": user.merchant.business_name, "business_category": user.merchant.business_category,
                         "merchant_code": user.merchant.merchant_code}
    return jsonable(d)


@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if body.role == Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin accounts cannot be created through registration")
    email = body.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email is already registered")
    if db.query(User).filter(User.phone == body.phone).first():
        raise HTTPException(status_code=409, detail="Phone number is already registered")
    try:
        user = User(full_name=body.full_name.strip(), email=email, phone=body.phone,
                    password_hash=hash_secret(body.password), role=body.role, is_active=True)
        db.add(user)
        db.flush()
        wallet = Wallet(owner_id=user.id, wallet_number="TMP" + uuid.uuid4().hex[:12])
        db.add(wallet)
        db.flush()
        wallet.wallet_number = f"WAL-{1000000 + wallet.id}"
        db.add(Account(account_type=AccountType.MERCHANT_WALLET if body.role == Role.MERCHANT else AccountType.USER_WALLET,
                       wallet_id=wallet.id, name=f"{user.full_name} wallet"))
        if body.role == Role.MERCHANT:
            m = Merchant(user_id=user.id, business_name=body.business_name, business_category=body.business_category,
                         merchant_code="TMP" + uuid.uuid4().hex[:12])
            db.add(m)
            db.flush()
            m.merchant_code = f"MER-{10000 + m.id}"
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or phone number is already registered")
    db.refresh(user)
    return user_dict(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if user is None or not verify_secret(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive. Contact support")
    background_tasks.add_task(send_email, user.email, "New login to your wallet account",
                              f"Hi {user.full_name}, a login to your account happened at {utcnow():%Y-%m-%d %H:%M} UTC. "
                              f"If this wasn't you, contact support immediately.")
    return TokenResponse(access_token=create_access_token(user.id, user.role.value), token_type="bearer",
                         expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_dict(user)
