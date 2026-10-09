from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Supplier
from app.schemas import SupplierCreate,SupplierOut
from app.auth.dependencies import require_roles
from app.services.audit import audit
from app.utils.validation import validate_phone,validate_gst
router=APIRouter(tags=["Suppliers"])
@router.post("/suppliers",response_model=SupplierOut,status_code=201)
def create(d:SupplierCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    validate_phone(d.phone); validate_gst(d.gst_number)
    if db.scalar(select(Supplier).where((Supplier.supplier_code==d.supplier_code)|(Supplier.email==d.email))):raise HTTPException(409,"Supplier code or email exists")
    x=Supplier(**d.model_dump(),created_by=u.id);db.add(x);db.flush();audit(db,u.id,"create","Supplier",x.id,new=d.model_dump());db.commit();db.refresh(x);return x
@router.get("/suppliers",response_model=list[SupplierOut])
def list_(skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):return db.scalars(select(Supplier).offset(skip).limit(limit)).all()
@router.get("/suppliers/{id}",response_model=SupplierOut)
def get(id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager","Warehouse Staff"))):
    x=db.get(Supplier,id)
    if not x:raise HTTPException(404,"Supplier not found")
    return x
@router.put("/suppliers/{id}",response_model=SupplierOut)
def update(id:int,d:SupplierCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Supplier,id)
    if not x:raise HTTPException(404,"Supplier not found")
    validate_phone(d.phone);validate_gst(d.gst_number)
    for k,v in d.model_dump().items():setattr(x,k,v)
    audit(db,u.id,"update","Supplier",x.id);db.commit();db.refresh(x);return x
@router.delete("/suppliers/{id}",status_code=204)
def delete(id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin"))):
    x=db.get(Supplier,id)
    if not x:raise HTTPException(404,"Supplier not found")
    x.is_active=False;audit(db,u.id,"delete","Supplier",x.id);db.commit()
