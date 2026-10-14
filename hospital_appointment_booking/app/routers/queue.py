import asyncio
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models import Appointment, Doctor, User
from app.auth.security import decode_token
from app.auth.dependencies import require_roles, get_current_user

router=APIRouter(tags=["Live Queue"])
queue_clients: dict[int,set[WebSocket]]={}
notification_clients: dict[int,set[WebSocket]]={}

async def broadcast_queue(doctor_id:int):
    db=SessionLocal()
    try:
        doc=db.get(Doctor,doctor_id)
        rows=db.scalars(select(Appointment).where(Appointment.doctor_id==doctor_id,Appointment.appointment_date==date.today(),Appointment.status.in_(["Checked-In","In Consultation"])).order_by(Appointment.token_number)).all()
        current=next((x.token_number for x in rows if x.status=="In Consultation"),None)
        waiting=sum(x.status=="Checked-In" for x in rows)
        payload={"doctor_id":doctor_id,"date":str(date.today()),"current_token":current,"waiting_count":waiting,"queue":[{"token":x.token_number,"status":x.status,"patient_id":x.patient_id,"position":i+1,"estimated_wait_minutes":i*(doc.slot_duration_minutes if doc else 15)} for i,x in enumerate([r for r in rows if r.status=="Checked-In"])]}
        dead=[]
        for ws in list(queue_clients.get(doctor_id,set())):
            try: await ws.send_json(payload)
            except Exception: dead.append(ws)
        for ws in dead: queue_clients[doctor_id].discard(ws)
    finally: db.close()

@router.websocket("/ws/queue/{doctor_id}")
async def queue_ws(ws:WebSocket,doctor_id:int,token:str):
    try:
        payload=decode_token(token,"access"); uid=int(payload["sub"])
        db=SessionLocal(); user=db.get(User,uid); doctor=db.get(Doctor,doctor_id)
        allowed=user and user.is_active and doctor and (user.role in ("admin","patient") or (user.role=="doctor" and doctor.user_id==user.id))
        db.close()
        if not allowed: await ws.close(code=1008); return
    except Exception:
        await ws.close(code=1008); return
    await ws.accept(); queue_clients.setdefault(doctor_id,set()).add(ws)
    try:
        await broadcast_queue(doctor_id)
        while True: await ws.receive_text()
    except WebSocketDisconnect:
        queue_clients.get(doctor_id,set()).discard(ws)

@router.websocket("/ws/notifications")
async def notification_ws(ws:WebSocket,token:str):
    try:
        payload=decode_token(token,"access"); uid=int(payload["sub"])
        db=SessionLocal(); user=db.get(User,uid); db.close()
        if not user or not user.is_active: await ws.close(code=1008); return
    except Exception:
        await ws.close(code=1008); return
    await ws.accept(); notification_clients.setdefault(uid,set()).add(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect:
        notification_clients.get(uid,set()).discard(ws)

@router.put("/doctors/me/call-next")
async def call_next(db:Session=Depends(get_db),user:User=Depends(require_roles("doctor"))):
    doctor=db.scalar(select(Doctor).where(Doctor.user_id==user.id))
    if not doctor: raise HTTPException(404,"Doctor profile not found")
    current=db.scalar(select(Appointment).where(Appointment.doctor_id==doctor.id,Appointment.appointment_date==date.today(),Appointment.status=="In Consultation"))
    if current: raise HTTPException(409,"Complete the current consultation before calling next")
    nxt=db.scalar(select(Appointment).where(Appointment.doctor_id==doctor.id,Appointment.appointment_date==date.today(),Appointment.status=="Checked-In").order_by(Appointment.token_number))
    if not nxt: raise HTTPException(404,"No checked-in patients waiting")
    nxt.status="In Consultation"; db.commit()
    await broadcast_queue(doctor.id)
    for ws in list(notification_clients.get(nxt.patient_id,set())):
        try: await ws.send_json({"type":"turn_next","message":"You are next, please be ready","appointment_id":nxt.id,"token_number":nxt.token_number})
        except Exception: notification_clients[nxt.patient_id].discard(ws)
    return {"message":"Next patient called","appointment_id":nxt.id,"token_number":nxt.token_number}
