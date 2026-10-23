from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import (ADMIN, CUSTOMER, create_access_token, get_current_user, hash_password,
                               require_roles, verify_password)
from app.database import get_db
from app.models import DeliveryPartner, Notification, User
from app.schemas.schemas import LoginIn, RegisterIn
from app.utils.common import row_dict

router = APIRouter(tags=["Auth"])


def user_out(u: User) -> dict:
    return row_dict(u, exclude=("password_hash",))


@router.post("/auth/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if data.role == ADMIN:
        raise HTTPException(403, "Admin accounts cannot be created through public registration")
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email already registered")
    if data.role == "delivery_partner" and db.query(DeliveryPartner).filter(
            DeliveryPartner.vehicle_number == data.vehicle_number.upper()).first():
        raise HTTPException(409, "Vehicle number already registered")
    user = User(name=data.name, email=email, phone=data.phone, password_hash=hash_password(data.password),
                role=data.role, is_approved=(data.role == CUSTOMER))  # owners/partners need admin approval
    try:
        db.add(user)
        db.flush()
        if data.role == "delivery_partner":
            db.add(DeliveryPartner(user_id=user.id, vehicle_type=data.vehicle_type,
                                   vehicle_number=data.vehicle_number.upper()))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email or vehicle number already registered")
    db.refresh(user)
    return user_out(user)


@router.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is inactive")
    return {"access_token": create_access_token(user), "token_type": "bearer", "expires_in_minutes": 30,
            "user": user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.put("/admin/users/{user_id}/approve")
def approve_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles(ADMIN))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.role not in ("restaurant_owner", "delivery_partner"):
        raise HTTPException(400, "Only restaurant owners and delivery partners need approval")
    user.is_approved = True
    if user.partner_profile:
        user.partner_profile.is_approved = True
    db.commit()
    return user_out(user)


@router.get("/admin/notifications")
def admin_notifications(skip: int = 0, limit: int = 20, db: Session = Depends(get_db),
                        _: User = Depends(require_roles(ADMIN))):
    q = db.query(Notification).filter(Notification.target_role == "admin").order_by(Notification.id.desc())
    return {"total": q.count(), "items": [row_dict(n) for n in q.offset(skip).limit(limit)]}
