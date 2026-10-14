
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Doctor, Department
from app.schemas import AdminCreateDoctorIn
from app.auth.security import hash_password
from app.auth.dependencies import require_roles
from app.services.notifications import send_doctor_account_email

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/doctors", status_code=status.HTTP_201_CREATED)
def create_doctor_account(
    data: AdminCreateDoctorIn,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Create a doctor account and profile, then notify the doctor by email."""

    if db.scalar(select(User.id).where(User.email == data.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    department = db.get(Department, data.department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    try:
        user = User(
            name=data.name,
            email=data.email,
            phone=data.phone,
            password_hash=hash_password(data.password),
            role="doctor",
            is_active=data.is_active,
        )
        db.add(user)
        db.flush()

        doctor = Doctor(
            user_id=user.id,
            name=data.name,
            department_id=data.department_id,
            specialization=data.specialization,
            qualification=data.qualification,
            experience_years=data.experience_years,
            consultation_fee=data.consultation_fee,
            slot_duration_minutes=data.slot_duration_minutes,
            is_active=data.is_active,
        )
        db.add(doctor)

        db.commit()
        db.refresh(user)
        db.refresh(doctor)

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create doctor; check duplicate email or profile",
        ) from exc

    except Exception:
        db.rollback()
        raise

    # Send the notification only after the account is committed.
    if user.email:
        bg.add_task(
            send_doctor_account_email,
            user.name,
            user.email,
        )

    return {
        "message": "Doctor account and profile created successfully",
        "email_notification": "Scheduled",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
        "doctor": {
            "id": doctor.id,
            "user_id": doctor.user_id,
            "department_id": doctor.department_id,
            "specialization": doctor.specialization,
            "qualification": doctor.qualification,
            "experience_years": doctor.experience_years,
            "consultation_fee": doctor.consultation_fee,
            "slot_duration_minutes": doctor.slot_duration_minutes,
            "is_active": doctor.is_active,
        },
    }
