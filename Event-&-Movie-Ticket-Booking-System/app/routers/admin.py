from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.security import hash_password
from app.database import get_db
from app.models.enums import Role
from app.models.user import User
from app.models.venue import Venue
from app.schemas.user import StaffCreate, UserOut

router = APIRouter(prefix="/admin", tags=["Admin"])
admin_only = require_roles(Role.ADMIN)


@router.get("/organizers/pending", response_model=List[UserOut])
def pending_organizers(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return (db.query(User).filter(User.role == Role.ORGANIZER.value, User.is_approved.is_(False))
            .order_by(User.id).all())


@router.put("/organizers/{user_id}/approve", response_model=UserOut)
def approve_organizer(user_id: int, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    user = db.get(User, user_id)
    if not user or user.role != Role.ORGANIZER.value:
        raise HTTPException(status_code=404, detail="Organizer not found")
    user.is_approved = True
    db.commit()
    db.refresh(user)
    return user


@router.post("/staff", response_model=UserOut, status_code=201)
def create_staff(payload: StaffCreate, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    venue = db.get(Venue, payload.venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    email = payload.email.lower()
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email is already registered")
    staff = User(name=payload.name, email=email, phone=payload.phone,
                 password_hash=hash_password(payload.password), role=Role.STAFF.value,
                 is_active=True, is_approved=True, venue_id=venue.id)
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff
