import os, uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Appointment, Doctor, Consultation, AppointmentFile, User
from app.schemas import ConsultationIn
from app.auth.dependencies import get_current_user
from app.config import settings
from app.services.booking import change_status
from app.services.notifications import send_email

router=APIRouter(tags=["Consultations & Files"])

def get_appointment_for_user(db, aid, user):
    a=db.get(Appointment,aid)
    if not a: raise HTTPException(404,"Appointment not found")
    if user.role=="patient" and a.patient_id!=user.id: raise HTTPException(403,"Not your appointment")
    if user.role=="doctor":
        d=db.scalar(select(Doctor).where(Doctor.user_id==user.id))
        if not d or a.doctor_id!=d.id: raise HTTPException(403,"Not your patient")
    return a

@router.post("/appointments/{appointment_id}/consultation")
def create_consultation(appointment_id:int,data:ConsultationIn,bg:BackgroundTasks,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    a=get_appointment_for_user(db,appointment_id,user)
    d=db.scalar(select(Doctor).where(Doctor.id==a.doctor_id))
    if user.role!="doctor" or d.user_id!=user.id: raise HTTPException(403,"Only the assigned doctor can write a consultation")
    if a.status!="In Consultation": raise HTTPException(400,"Appointment must be In Consultation")
    if a.consultation: raise HTTPException(409,"Consultation already exists")
    obj=Consultation(appointment_id=a.id,**data.model_dump()); db.add(obj); change_status(db,a,"Completed",user.id); db.commit(); db.refresh(obj)
    bg.add_task(send_email,a.patient.email,"Consultation completed",f"Your consultation with Dr. {d.name} is complete. Follow-up: {data.follow_up_date or 'Not specified'}.")
    return obj

@router.get("/appointments/{appointment_id}/consultation")
def get_consultation(appointment_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    a=get_appointment_for_user(db,appointment_id,user)
    if not a.consultation: raise HTTPException(404,"Consultation not found")
    return a.consultation

@router.post("/appointments/{appointment_id}/files",status_code=201)
async def upload_file(appointment_id:int,file_type:str,bg:BackgroundTasks,file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    a=get_appointment_for_user(db,appointment_id,user)
    if file_type not in ("Lab Report","Prescription","Scan"): raise HTTPException(422,"Invalid file_type")
    if user.role=="patient" and file_type!="Lab Report": raise HTTPException(403,"Patients may upload lab reports only")
    if user.role=="doctor" and file_type=="Lab Report": raise HTTPException(403,"Doctors may upload prescriptions or scans")
    ext=Path(file.filename or "").suffix.lower()
    if ext not in (".pdf",".jpg",".jpeg",".png"): raise HTTPException(415,"Only PDF, JPG and PNG files are supported")
    content=await file.read()
    if len(content)>5*1024*1024: raise HTTPException(413,"Maximum file size is 5 MB")
    os.makedirs(settings.UPLOAD_DIR,exist_ok=True); stored=f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.UPLOAD_DIR,stored),"wb") as out: out.write(content)
    obj=AppointmentFile(appointment_id=a.id,uploaded_by=user.id,file_type=file_type,original_name=file.filename or "upload",stored_name=stored,size_kb=round(len(content)/1024,2))
    db.add(obj); db.commit(); db.refresh(obj); return obj

@router.get("/appointments/{appointment_id}/files")
def list_files(appointment_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    a=get_appointment_for_user(db,appointment_id,user)
    return a.files

@router.get("/files/{file_id}/download")
def download(file_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    f=db.get(AppointmentFile,file_id)
    if not f: raise HTTPException(404,"File not found")
    a=f.appointment
    if user.role=="patient" and a.patient_id!=user.id: raise HTTPException(403,"Not your file")
    if user.role=="doctor":
        d=db.scalar(select(Doctor).where(Doctor.user_id==user.id))
        if not d or a.doctor_id!=d.id: raise HTTPException(403,"Not your patient file")
    path=os.path.join(settings.UPLOAD_DIR,f.stored_name)
    if not os.path.isfile(path): raise HTTPException(404,"File missing from storage")
    return FileResponse(path,filename=f.original_name)

@router.get("/patients/me/history")
def history(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if user.role!="patient": raise HTTPException(403,"Patients only")
    return db.scalars(select(Appointment).where(Appointment.patient_id==user.id).order_by(Appointment.appointment_date.desc())).all()
