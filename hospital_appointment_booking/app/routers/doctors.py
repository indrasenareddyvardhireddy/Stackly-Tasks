from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Doctor, User, Schedule, DoctorLeave, Appointment
from app.schemas import DoctorIn, ScheduleIn, LeaveIn
from app.auth.dependencies import get_current_user, require_roles

router=APIRouter(tags=["Doctors"])



@router.get("/doctors")
def list_doctors(department_id:int|None=None,specialization:str|None=None,name:str|None=None,skip:int=0,limit:int=50,db:Session=Depends(get_db)):
    q=select(Doctor).where(Doctor.is_active.is_(True))
    if department_id: q=q.where(Doctor.department_id==department_id)
    if specialization: q=q.where(Doctor.specialization.ilike(f"%{specialization}%"))
    if name: q=q.where(Doctor.name.ilike(f"%{name}%"))
    return db.scalars(q.offset(skip).limit(min(limit,100))).all()

@router.get("/doctors/{doctor_id}")
def get_doctor(doctor_id:int,db:Session=Depends(get_db)):
    obj=db.get(Doctor,doctor_id)
    if not obj or not obj.is_active: raise HTTPException(404,"Doctor not found")
    return obj

@router.put("/doctors/{doctor_id}")
def update_doctor(doctor_id:int,data:DoctorIn,db:Session=Depends(get_db),_=Depends(require_roles("admin"))):
    obj=db.get(Doctor,doctor_id)
    if not obj: raise HTTPException(404,"Doctor not found")
    if not data.is_active and db.scalar(select(Appointment.id).where(Appointment.doctor_id==doctor_id,Appointment.appointment_date>=date.today(),Appointment.status.in_(["Booked","Checked-In","In Consultation"]))): raise HTTPException(409,"Doctor has upcoming appointments")
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    db.commit(); db.refresh(obj); return obj

@router.delete("/doctors/{doctor_id}")
def deactivate_doctor(doctor_id:int,db:Session=Depends(get_db),_=Depends(require_roles("admin"))):
    obj=db.get(Doctor,doctor_id)
    if not obj: raise HTTPException(404,"Doctor not found")
    if db.scalar(select(Appointment.id).where(Appointment.doctor_id==doctor_id,Appointment.appointment_date>=date.today(),Appointment.status=="Booked")): raise HTTPException(409,"Doctor has upcoming appointments")
    obj.is_active=False; db.commit(); return {"message":"Doctor deactivated"}

@router.post("/doctors/{doctor_id}/schedules",status_code=201)
def add_schedule(doctor_id:int,data:ScheduleIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    doctor=db.get(Doctor,doctor_id)
    if not doctor: raise HTTPException(404,"Doctor not found")
    if user.role!="admin" and not (user.role=="doctor" and doctor.user_id==user.id): raise HTTPException(403,"Not your schedule")
    if data.end_time<=data.start_time: raise HTTPException(400,"End time must be after start time")
    if (data.break_start is None)!=(data.break_end is None): raise HTTPException(400,"Provide both break times")
    if data.break_start and not (data.start_time<=data.break_start<data.break_end<=data.end_time): raise HTTPException(400,"Break must be inside working hours")
    for old in db.scalars(select(Schedule).where(Schedule.doctor_id==doctor_id,Schedule.day_of_week==data.day_of_week)).all():
        if data.start_time<old.end_time and old.start_time<data.end_time: raise HTTPException(409,"Schedule overlaps an existing schedule")
    obj=Schedule(doctor_id=doctor_id,**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@router.get("/doctors/{doctor_id}/schedules")
def list_schedules(doctor_id:int,db:Session=Depends(get_db)):
    return db.scalars(select(Schedule).where(Schedule.doctor_id==doctor_id)).all()

@router.put("/schedules/{schedule_id}")
def update_schedule(schedule_id:int,data:ScheduleIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    obj=db.get(Schedule,schedule_id)
    if not obj: raise HTTPException(404,"Schedule not found")
    doctor=db.get(Doctor,obj.doctor_id)
    if user.role!="admin" and not (user.role=="doctor" and doctor.user_id==user.id): raise HTTPException(403,"Not your schedule")
    if data.end_time<=data.start_time: raise HTTPException(400,"End time must be after start time")
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    db.commit(); db.refresh(obj); return obj

@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    obj=db.get(Schedule,schedule_id)
    if not obj: raise HTTPException(404,"Schedule not found")
    doctor=db.get(Doctor,obj.doctor_id)
    if user.role!="admin" and not (user.role=="doctor" and doctor.user_id==user.id): raise HTTPException(403,"Not your schedule")
    db.delete(obj); db.commit(); return {"message":"Schedule deleted"}

@router.post("/doctors/{doctor_id}/leaves",status_code=201)
def add_leave(doctor_id:int,data:LeaveIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    doctor=db.get(Doctor,doctor_id)
    if not doctor: raise HTTPException(404,"Doctor not found")
    if user.role!="admin" and not (user.role=="doctor" and doctor.user_id==user.id): raise HTTPException(403,"Not your leave calendar")
    leave=DoctorLeave(doctor_id=doctor_id,**data.model_dump()); db.add(leave)
    appointments=db.scalars(select(Appointment).where(Appointment.doctor_id==doctor_id,Appointment.appointment_date==data.leave_date,Appointment.status=="Booked")).all()
    for a in appointments: a.status="Cancelled"
    db.commit()
    return {"leave":leave,"cancelled_appointments":len(appointments),"note":"Configure SMTP to email affected patients"}

@router.get("/doctors/{doctor_id}/leaves")
def list_leaves(doctor_id:int,db:Session=Depends(get_db)):
    return db.scalars(select(DoctorLeave).where(DoctorLeave.doctor_id==doctor_id)).all()

@router.get("/doctors/{doctor_id}/available-slots")
def available_slots(doctor_id:int,date:date,db:Session=Depends(get_db)):
    doctor=db.get(Doctor,doctor_id)
    if not doctor or not doctor.is_active: raise HTTPException(404,"Doctor not found")
    if db.scalar(select(DoctorLeave.id).where(DoctorLeave.doctor_id==doctor_id,DoctorLeave.leave_date==date)): return {"date":str(date),"slots":[]}
    schedules=db.scalars(select(Schedule).where(Schedule.doctor_id==doctor_id,Schedule.day_of_week==date.weekday())).all()
    booked=set(db.scalars(select(Appointment.slot_time).where(Appointment.doctor_id==doctor_id,Appointment.appointment_date==date,Appointment.status.not_in(["Cancelled","No-Show"]))).all())
    now=datetime.now(); slots=[]
    for s in schedules:
        current=datetime.combine(date,s.start_time); end=datetime.combine(date,s.end_time)
        while current+timedelta(minutes=doctor.slot_duration_minutes)<=end:
            t=current.time()
            if (not s.break_start or not (s.break_start<=t<s.break_end)) and t not in booked and current>now:
                slots.append(t.strftime("%H:%M:%S"))
            current+=timedelta(minutes=doctor.slot_duration_minutes)
    return {"doctor_id":doctor_id,"date":str(date),"slots":sorted(set(slots))}
