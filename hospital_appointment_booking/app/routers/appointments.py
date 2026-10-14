
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Appointment,
    Doctor,
    User,
    AppointmentHistory,
)
from app.schemas import AppointmentIn, RescheduleIn
from app.auth.dependencies import get_current_user, require_roles
from app.services.booking import validate_slot, change_status
from app.services.notifications import (
    appointment_email,
    send_appointment_booking_emails,
    send_appointment_cancellation_emails,
    send_appointment_rescheduled_emails,
)

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("", status_code=201)
def book(
    data: AppointmentIn,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("patient")),
):
    doctor = db.scalar(
        select(Doctor).where(
            Doctor.id == data.doctor_id,
            Doctor.is_active.is_(True),
        )
    )

    if not doctor:
        raise HTTPException(404, "Active doctor not found")

    # Lock the doctor row to reduce simultaneous booking conflicts.
    db.scalar(
        select(Doctor)
        .where(Doctor.id == doctor.id)
        .with_for_update()
    )

    validate_slot(db, doctor, data.appointment_date, data.slot_time)

    existing_same_time = db.scalar(
        select(Appointment.id).where(
            Appointment.patient_id == user.id,
            Appointment.appointment_date == data.appointment_date,
            Appointment.slot_time == data.slot_time,
            Appointment.status.not_in(["Cancelled", "No-Show"]),
        )
    )

    if existing_same_time:
        raise HTTPException(
            409, "You already have an appointment at this time"
        )

    existing_same_doctor = db.scalar(
        select(Appointment.id).where(
            Appointment.patient_id == user.id,
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == data.appointment_date,
            Appointment.status.not_in(["Cancelled", "No-Show"]),
        )
    )

    if existing_same_doctor:
        raise HTTPException(
            409, "Only one appointment per doctor per day"
        )

    count = (
        db.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_date == data.appointment_date,
                Appointment.status.not_in(["Cancelled", "No-Show"]),
            )
        )
        or 0
    )

    # Generate appointment number without nested f-string syntax errors.
    daily_count = (
        db.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.appointment_date == data.appointment_date
            )
        )
        or 0
    )

    number = (
        f"APT-{data.appointment_date:%Y%m%d}-{daily_count + 1:04d}"
    )

    appointment = Appointment(
        appointment_number=number,
        patient_id=user.id,
        doctor_id=doctor.id,
        appointment_date=data.appointment_date,
        slot_time=data.slot_time,
        token_number=count + 1,
        reason=data.reason,
        consultation_fee=doctor.consultation_fee,
    )

    db.add(appointment)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            409, "Slot conflict; please choose another slot"
        ) from exc

    db.refresh(appointment)

    # Send booking confirmation to patient and notification to doctor.
    doctor_user = db.get(User, doctor.user_id)

    if user.email:
        if doctor_user and doctor_user.email:
            bg.add_task(
                send_appointment_booking_emails,
                user.email,
                doctor_user.email,
                appointment,
                doctor.name,
            )
        else:
            bg.add_task(
                appointment_email,
                user.email,
                "Appointment Booking Confirmation",
                appointment,
                doctor.name,
            )

    return appointment


@router.get("")
def list_appointments(
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    doctor_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    appointment_number: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Appointment)

    if user.role == "patient":
        query = query.where(Appointment.patient_id == user.id)

    elif user.role == "doctor":
        doctor = db.scalar(
            select(Doctor).where(Doctor.user_id == user.id)
        )

        if not doctor:
            return []

        query = query.where(Appointment.doctor_id == doctor.id)

    if status:
        query = query.where(Appointment.status == status)

    if doctor_id and user.role == "admin":
        query = query.where(Appointment.doctor_id == doctor_id)

    if date_from:
        query = query.where(
            Appointment.appointment_date >= date_from
        )

    if date_to:
        query = query.where(
            Appointment.appointment_date <= date_to
        )

    if appointment_number:
        query = query.where(
            Appointment.appointment_number == appointment_number
        )

    return db.scalars(
        query.order_by(
            Appointment.appointment_date,
            Appointment.slot_time,
        )
        .offset(skip)
        .limit(min(limit, 100))
    ).all()


@router.get("/{appointment_id}")
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    appointment = db.get(Appointment, appointment_id)

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    if (
        user.role == "patient"
        and appointment.patient_id != user.id
    ):
        raise HTTPException(403, "Not your appointment")

    if user.role == "doctor":
        doctor = db.scalar(
            select(Doctor).where(Doctor.user_id == user.id)
        )

        if not doctor or appointment.doctor_id != doctor.id:
            raise HTTPException(403, "Not your patient")

    return appointment


@router.put("/{appointment_id}/cancel")
def cancel(
    appointment_id: int,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    appointment = db.get(Appointment, appointment_id)

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    if user.role != "admin" and not (
        user.role == "patient"
        and appointment.patient_id == user.id
    ):
        raise HTTPException(403, "Not allowed")

    if appointment.status != "Booked":
        raise HTTPException(
            400, "Only Booked appointments can be cancelled"
        )

    if user.role == "patient":
        start = datetime.combine(
            appointment.appointment_date,
            appointment.slot_time,
        )

        if start - datetime.now() < timedelta(hours=2):
            raise HTTPException(
                400, "Cancellation allowed only 2 hours before appointment"
            )

    change_status(db, appointment, "Cancelled", user.id)
    db.commit()
    db.refresh(appointment)

    doctor = db.get(Doctor, appointment.doctor_id)
    doctor_user = db.get(User, doctor.user_id) if doctor else None
    patient = db.get(User, appointment.patient_id)

    if patient and patient.email:
        if doctor and doctor_user and doctor_user.email:
            bg.add_task(
                send_appointment_cancellation_emails,
                patient.email,
                doctor_user.email,
                appointment,
                doctor.name,
            )
        else:
            bg.add_task(
                appointment_email,
                patient.email,
                "Appointment Cancellation Confirmation",
                appointment,
                doctor.name if doctor else "Your doctor",
            )

    return {
        "message": "Appointment cancelled",
        "appointment": appointment,
    }


@router.put("/{appointment_id}/reschedule")
def reschedule(
    appointment_id: int,
    data: RescheduleIn,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("patient")),
):
    appointment = db.get(Appointment, appointment_id)

    if not appointment or appointment.patient_id != user.id:
        raise HTTPException(404, "Appointment not found")

    if appointment.status != "Booked":
        raise HTTPException(
            400, "Only Booked appointments can be rescheduled"
        )

    if appointment.reschedule_count >= 2:
        raise HTTPException(400, "Maximum reschedules reached")

    start = datetime.combine(
        appointment.appointment_date,
        appointment.slot_time,
    )

    if start - datetime.now() < timedelta(hours=2):
        raise HTTPException(
            400, "Reschedule allowed only 2 hours before appointment"
        )

    doctor = db.get(Doctor, appointment.doctor_id)

    if not doctor:
        raise HTTPException(404, "Doctor not found")

    validate_slot(db, doctor, data.appointment_date, data.slot_time)

    old_appointment_id = appointment.id
    appointment.status = "Cancelled"
    db.flush()

    count = (
        db.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_date == data.appointment_date,
                Appointment.status.not_in(["Cancelled", "No-Show"]),
            )
        )
        or 0
    )

    daily_count = (
        db.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.appointment_date == data.appointment_date
            )
        )
        or 0
    )

    new_appointment = Appointment(
        appointment_number=(
            f"APT-{data.appointment_date:%Y%m%d}-{daily_count + 1:04d}"
        ),
        patient_id=user.id,
        doctor_id=doctor.id,
        appointment_date=data.appointment_date,
        slot_time=data.slot_time,
        token_number=count + 1,
        reason=appointment.reason,
        status="Booked",
        consultation_fee=appointment.consultation_fee,
        reschedule_count=appointment.reschedule_count + 1,
    )

    db.add(new_appointment)

    db.add(
        AppointmentHistory(
            appointment_id=old_appointment_id,
            old_status="Booked",
            new_status="Cancelled",
            changed_by=user.id,
        )
    )

    db.commit()
    db.refresh(new_appointment)

    doctor_user = db.get(User, doctor.user_id)

    if user.email:
        if doctor_user and doctor_user.email:
            bg.add_task(
                send_appointment_rescheduled_emails,
                user.email,
                doctor_user.email,
                new_appointment,
                doctor.name,
            )
        else:
            bg.add_task(
                appointment_email,
                user.email,
                "Appointment Rescheduled",
                new_appointment,
                doctor.name,
            )

    return {
        "message": "Appointment rescheduled",
        "previous_appointment_id": old_appointment_id,
        "appointment": new_appointment,
    }


@router.put("/{appointment_id}/check-in")
def check_in(
    appointment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    appointment = db.get(Appointment, appointment_id)

    if not appointment:
        raise HTTPException(404, "Appointment not found")

    if appointment.status != "Booked":
        raise HTTPException(
            400, "Only Booked appointments can be checked in"
        )

    now = datetime.now()

    appointment_start = datetime.combine(
        appointment.appointment_date,
        appointment.slot_time,
    )

    if (
        now.date() != appointment.appointment_date
        or now < appointment_start - timedelta(minutes=30)
    ):
        raise HTTPException(
            400,
            "Check-in opens 30 minutes before the slot on appointment day",
        )

    change_status(db, appointment, "Checked-In", user.id)
    db.commit()

    return {
        "message": "Patient checked in",
        "appointment": appointment,
    }
