from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserOut, Login, Token
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_current_user, require_roles
from app.services.audit import audit
router=APIRouter(prefix="/auth",tags=["Authentication"])

@router.post("/register",response_model=UserOut,status_code=201)
def register(data:UserCreate,db:Session=Depends(get_db),admin=Depends(require_roles("Admin"))):
    if data.role not in ["Admin","Inventory Manager","Warehouse Staff"]: raise HTTPException(422,"Invalid role")
    if db.scalar(select(User).where((User.username==data.username)|(User.email==data.email))): raise HTTPException(409,"Username or email already exists")
    if data.role=="Warehouse Staff" and not data.warehouse_id: raise HTTPException(422,"Warehouse Staff must be assigned a warehouse")
    u=User(username=data.username,email=data.email,password_hash=hash_password(data.password),role=data.role,warehouse_id=data.warehouse_id,created_by=admin.id)
    db.add(u); db.flush(); audit(db,admin.id,"create","User",u.id,new={"username":u.username,"role":u.role}); db.commit(); db.refresh(u); return u

@router.post("/login",response_model=Token)
def login(data:Login,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.username==data.username))
    if not u or not verify_password(data.password,u.password_hash): raise HTTPException(401,"Invalid credentials")
    if not u.is_active: raise HTTPException(403,"Inactive user")
    return Token(access_token=create_access_token({"sub":str(u.id),"role":u.role}))

@router.get("/me",response_model=UserOut)
def me(user=Depends(get_current_user)): return user
