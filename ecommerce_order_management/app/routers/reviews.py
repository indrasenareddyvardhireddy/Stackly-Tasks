from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.review import Review
from app.schemas.review import ReviewUpdate
from app.models.user import UserRole
from app.auth.dependencies import require_role
router=APIRouter(prefix="/reviews",tags=["Reviews"])

@router.put("/{review_id}")
def update(review_id:int,data:ReviewUpdate,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    r=db.scalar(select(Review).where(Review.id==review_id,Review.customer_id==user.id))
    if not r: raise HTTPException(404,"Review not found")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(r,k,v)
    db.commit(); db.refresh(r); return r

@router.delete("/{review_id}")
def delete(review_id:int,db:Session=Depends(get_db),user=Depends(require_role(UserRole.Customer))):
    r=db.scalar(select(Review).where(Review.id==review_id,Review.customer_id==user.id))
    if not r: raise HTTPException(404,"Review not found")
    db.delete(r); db.commit(); return {"message":"Review deleted"}
