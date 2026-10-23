from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import CUSTOMER, require_roles
from app.database import get_db
from app.models import Address, User
from app.schemas.schemas import AddressIn, AddressUpdate
from app.utils.common import row_dict

router = APIRouter(prefix="/addresses", tags=["Addresses"])


def _own(db, address_id, user) -> Address:
    a = db.get(Address, address_id)
    if not a or a.customer_id != user.id:
        raise HTTPException(404, "Address not found")
    return a


def _set_default(db, user, address):
    db.query(Address).filter(Address.customer_id == user.id).update({"is_default": False})
    address.is_default = True


@router.post("", status_code=201)
def create_address(data: AddressIn, db: Session = Depends(get_db), user: User = Depends(require_roles(CUSTOMER))):
    has_any = db.query(Address).filter(Address.customer_id == user.id).count() > 0
    a = Address(customer_id=user.id, **data.model_dump(exclude={"is_default"}))
    db.add(a)
    db.flush()
    if data.is_default or not has_any:  # first address becomes default
        _set_default(db, user, a)
    db.commit()
    return row_dict(a)


@router.get("")
def list_addresses(db: Session = Depends(get_db), user: User = Depends(require_roles(CUSTOMER))):
    return [row_dict(a) for a in db.query(Address).filter(Address.customer_id == user.id)
            .order_by(Address.is_default.desc(), Address.id)]


@router.put("/{address_id}")
def update_address(address_id: int, data: AddressUpdate, db: Session = Depends(get_db),
                   user: User = Depends(require_roles(CUSTOMER))):
    a = _own(db, address_id, user)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    return row_dict(a)


@router.delete("/{address_id}")
def delete_address(address_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(CUSTOMER))):
    a = _own(db, address_id, user)
    was_default = a.is_default
    try:
        db.delete(a)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Address is used by existing orders and cannot be deleted")
    if was_default:
        nxt = db.query(Address).filter(Address.customer_id == user.id).order_by(Address.id).first()
        if nxt:
            nxt.is_default = True
    db.commit()
    return {"message": "Address deleted"}


@router.put("/{address_id}/default")
def make_default(address_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(CUSTOMER))):
    a = _own(db, address_id, user)
    _set_default(db, user, a)
    db.commit()
    return row_dict(a)
