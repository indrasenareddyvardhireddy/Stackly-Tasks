from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Customer
from app.schemas import CustomerCreate,CustomerOut
from app.auth.dependencies import require_roles
from app.services.audit import audit
from app.utils.validation import validate_phone
router=APIRouter(tags=["Customers"])
@router.post("/customers",response_model=CustomerOut,status_code=201)
def create(d:CustomerCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    validate_phone(d.phone)
    if db.scalar(select(Customer).where((Customer.customer_code==d.customer_code)|(Customer.email==d.email))):raise HTTPException(409,"Customer code or email exists")
    x=Customer(**d.model_dump(),created_by=u.id);db.add(x);db.flush();audit(db,u.id,"create","Customer",x.id,new=d.model_dump());db.commit();db.refresh(x);return x
@router.get("/customers",response_model=list[CustomerOut])
def list_(skip:int=0,limit:int=50,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):return db.scalars(select(Customer).offset(skip).limit(limit)).all()
@router.get("/customers/{id}",response_model=CustomerOut)
def get(id:int,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Customer,id)
    if not x:raise HTTPException(404,"Customer not found")
    return x
@router.put("/customers/{id}",response_model=CustomerOut)
def update(id:int,d:CustomerCreate,db:Session=Depends(get_db),u=Depends(require_roles("Admin","Inventory Manager"))):
    x=db.get(Customer,id)
    if not x:raise HTTPException(404,"Customer not found")
    validate_phone(d.phone)
    for k,v in d.model_dump().items():setattr(x,k,v)
    audit(db,u.id,"update","Customer",x.id);db.commit();db.refresh(x);return x
