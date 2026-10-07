from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,update
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.address import Address
from app.models.user import UserRole
from app.schemas.address import AddressCreate,AddressResponse
from app.auth.dependencies import require_role
from app.utils.validators import validate_phone,validate_pincode
router=APIRouter(prefix="/addresses",tags=["Addresses"])

@router.post("",response_model=AddressResponse,status_code=201)
def create(data:AddressCreate,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    validate_phone(data.phone); validate_pincode(data.pincode)
    if data.is_default: db.execute(update(Address).where(Address.customer_id==user.id).values(is_default=False))
    obj=Address(customer_id=user.id,**data.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@router.get("",response_model=list[AddressResponse])
def list_addresses(db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    return db.scalars(select(Address).where(Address.customer_id==user.id)).all()

@router.put("/{address_id}",response_model=AddressResponse)
def update_address(address_id:int,data:AddressCreate,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    obj=db.scalar(select(Address).where(Address.id==address_id,Address.customer_id==user.id))
    if not obj: raise HTTPException(404,"Address not found")
    validate_phone(data.phone); validate_pincode(data.pincode)
    if data.is_default: db.execute(update(Address).where(Address.customer_id==user.id).values(is_default=False))
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    db.commit(); db.refresh(obj); return obj

@router.delete("/{address_id}")
def delete_address(address_id:int,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    obj=db.scalar(select(Address).where(Address.id==address_id,Address.customer_id==user.id))
    if not obj: raise HTTPException(404,"Address not found")
    db.delete(obj); db.commit(); return {"message":"Address deleted"}

@router.put("/{address_id}/default",response_model=AddressResponse)
def default(address_id:int,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    obj=db.scalar(select(Address).where(Address.id==address_id,Address.customer_id==user.id))
    if not obj: raise HTTPException(404,"Address not found")
    db.execute(update(Address).where(Address.customer_id==user.id).values(is_default=False)); obj.is_default=True
    db.commit(); db.refresh(obj); return obj
