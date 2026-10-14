from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Appointment, Doctor, DoctorLeave, Schedule, AppointmentHistory

def validate_slot(db: Session, doctor: Doctor, day, slot):
    now = datetime.now()
    target = datetime.combine(day, slot)
    if target <= now: raise HTTPException(400, "Appointments must be in the future")
    if day > now.date() + timedelta(days=30): raise HTTPException(400, "Appointments can be booked at most 30 days ahead")
    if db.scalar(select(DoctorLeave.id).where(DoctorLeave.doctor_id == doctor.id, DoctorLeave.leave_date == day)):
        raise HTTPException(409, "Doctor is on leave on this date")
    schedule = db.scalar(select(Schedule).where(Schedule.doctor_id == doctor.id, Schedule.day_of_week == day.weekday()))
    if not schedule or not (schedule.start_time <= slot < schedule.end_time):
        raise HTTPException(400, "Slot is outside doctor's working hours")
    if schedule.break_start and schedule.break_end and schedule.break_start <= slot < schedule.break_end:
        raise HTTPException(400, "Slot falls during the doctor's break")
    if slot.minute % doctor.slot_duration_minutes != 0:
        # Allow schedule-relative slot alignment in common hourly schedules; exact availability is still checked below.
        elapsed = (slot.hour * 60 + slot.minute) - (schedule.start_time.hour * 60 + schedule.start_time.minute)
        if elapsed % doctor.slot_duration_minutes != 0: raise HTTPException(400, "Slot does not align with the schedule")
    existing = db.scalar(select(Appointment.id).where(
        Appointment.doctor_id == doctor.id, Appointment.appointment_date == day,
        Appointment.slot_time == slot, Appointment.status.not_in(["Cancelled", "No-Show"])))
    if existing: raise HTTPException(409, "This slot is already booked")
    same_patient = db.scalar(select(Appointment.id).where(
        Appointment.patient_id == 0, Appointment.appointment_date == day, Appointment.slot_time == slot))
    return schedule

def change_status(db, appointment, new_status, user_id):
    old = appointment.status
    appointment.status = new_status
    db.add(AppointmentHistory(appointment_id=appointment.id, old_status=old, new_status=new_status, changed_by=user_id))
