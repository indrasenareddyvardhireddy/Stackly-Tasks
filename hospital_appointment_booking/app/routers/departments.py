from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Department, Doctor
from app.schemas import DepartmentIn
from app.auth.dependencies import require_roles

router = APIRouter(prefix="/departments", tags=["Departments"])

@router.post("", status_code=201)
def create(data: DepartmentIn, db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    if db.scalar(select(Department.id).where(Department.name == data.name)): raise HTTPException(409, "Department already exists")
    obj=Department(**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@router.get("")
def list_departments(skip: int=0, limit: int=50, db: Session=Depends(get_db)):
    return db.scalars(select(Department).offset(skip).limit(min(limit,100))).all()

@router.put("/{department_id}")
def update(department_id: int, data: DepartmentIn, db: Session=Depends(get_db), _=Depends(require_roles("admin"))):
    obj=db.get(Department,department_id)
    if not obj: raise HTTPException(404,"Department not found")
    obj.name=data.name; obj.description=data.description; db.commit(); db.refresh(obj); return obj

@router.delete("/{department_id}", status_code=204)
def delete(department_id: int, db: Session=Depends(get_db), _=Depends(require_roles("admin"))):
    obj=db.get(Department,department_id)
    if not obj: raise HTTPException(404,"Department not found")
    if db.scalar(select(Doctor.id).where(Doctor.department_id==department_id, Doctor.is_active.is_(True))): raise HTTPException(409,"Department has active doctors")
    db.delete(obj); db.commit()
