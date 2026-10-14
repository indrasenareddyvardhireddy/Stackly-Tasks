from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Appointment, Doctor, Department, User
from app.auth.dependencies import require_roles

router=APIRouter(prefix="/reports",tags=["Reports"])

@router.get("/dashboard")
def dashboard(db:Session=Depends(get_db),_=Depends(require_roles("admin"))):
    today=date.today()
    rows=db.scalars(select(Appointment).where(Appointment.appointment_date==today)).all()
    return {"date":str(today),"total_appointments":len(rows),"checked_in":sum(a.status=="Checked-In" for a in rows),"completed":sum(a.status=="Completed" for a in rows),"cancelled":sum(a.status=="Cancelled" for a in rows),"no_shows":sum(a.status=="No-Show" for a in rows),"consultation_revenue":sum(a.consultation_fee for a in rows if a.status=="Completed")}

@router.get("/doctor-performance")
def doctor_performance(date_from:date,date_to:date,db:Session=Depends(get_db),_=Depends(require_roles("admin"))):
    docs=db.scalars(select(Doctor)).all(); result=[]
    for d in docs:
        rows=db.scalars(select(Appointment).where(Appointment.doctor_id==d.id,Appointment.appointment_date>=date_from,Appointment.appointment_date<=date_to)).all()
        total=len(rows); completed=sum(x.status=="Completed" for x in rows); no_shows=sum(x.status=="No-Show" for x in rows)
        result.append({"doctor_id":d.id,"doctor_name":d.name,"appointments":total,"completed_consultations":completed,"no_show_percentage":round(no_shows*100/total,2) if total else 0,"revenue":sum(x.consultation_fee for x in rows if x.status=="Completed")})
    return result

@router.get("/department-summary")
def department_summary(date_from:date,date_to:date,db:Session=Depends(get_db),_=Depends(require_roles("admin"))):
    result=[]
    for dep in db.scalars(select(Department)).all():
        doctor_ids=select(Doctor.id).where(Doctor.department_id==dep.id)
        count=db.scalar(select(func.count()).select_from(Appointment).where(Appointment.doctor_id.in_(doctor_ids),Appointment.appointment_date>=date_from,Appointment.appointment_date<=date_to)) or 0
        result.append({"department_id":dep.id,"department":dep.name,"appointment_count":count})
    return result

@router.get("/peak-hours")
def peak_hours(date_from:date,date_to:date,db:Session=Depends(get_db),_=Depends(require_roles("admin"))):
    rows=db.execute(select(func.hour(Appointment.slot_time),func.count()).where(Appointment.appointment_date>=date_from,Appointment.appointment_date<=date_to).group_by(func.hour(Appointment.slot_time)).order_by(func.hour(Appointment.slot_time))).all()
    return [{"hour":int(h),"appointment_count":int(c)} for h,c in rows]

@router.get("/frequent-no-shows")
def frequent_no_shows(db:Session=Depends(get_db),_=Depends(require_roles("admin"))):
    since=date.today()-timedelta(days=90)
    rows=db.execute(select(User.id,User.name,User.email,func.count(Appointment.id).label("no_shows")).join(Appointment,Appointment.patient_id==User.id).where(Appointment.status=="No-Show",Appointment.appointment_date>=since).group_by(User.id,User.name,User.email).having(func.count(Appointment.id)>=3)).all()
    return [{"patient_id":r.id,"name":r.name,"email":r.email,"no_shows":r.no_shows} for r in rows]
