from datetime import datetime
from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditLog
from app.auth.dependencies import require_roles
router=APIRouter(prefix="/audit-logs",tags=["Audit Logs"])
@router.get("")
def logs(user_id:int|None=None,action:str|None=None,entity:str|None=None,skip:int=0,limit:int=100,db:Session=Depends(get_db),u=Depends(require_roles("Admin"))):
    q=select(AuditLog)
    if user_id:q=q.where(AuditLog.user_id==user_id)
    if action:q=q.where(AuditLog.action==action)
    if entity:q=q.where(AuditLog.entity_type==entity)
    return db.scalars(q.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)).all()
