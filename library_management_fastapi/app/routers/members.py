from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_admin

from app.schemas.member import (
    MemberCreate,
    MemberUpdate,
    MemberResponse
)

from app.services.member_service import (
    create_member,
    get_members,
    get_member,
    update_member,
    delete_member
)


router = APIRouter()


# =========================================================
# CREATE MEMBER + USER ACCOUNT
# ADMIN ONLY
# =========================================================

@router.post(
    "/",
    response_model=MemberResponse,
    status_code=201
)
def add_member(
    data: MemberCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    return create_member(db, data)


# =========================================================
# GET ALL MEMBERS
# ADMIN ONLY
# =========================================================

@router.get(
    "/",
    response_model=list[MemberResponse]
)
def all_members(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    return get_members(db, skip, limit)


# =========================================================
# GET MEMBER BY ID
# ADMIN ONLY
# =========================================================

@router.get(
    "/{member_id}",
    response_model=MemberResponse
)
def member_by_id(
    member_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    return get_member(db, member_id)


# =========================================================
# UPDATE MEMBER
# ADMIN ONLY
# =========================================================

@router.put(
    "/{member_id}",
    response_model=MemberResponse
)
def edit_member(
    member_id: int,
    data: MemberUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    return update_member(db, member_id, data)


# =========================================================
# DELETE MEMBER
# ADMIN ONLY
# =========================================================

@router.delete(
    "/{member_id}"
)
def remove_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):

    delete_member(db, member_id)

    return {
        "message": "Member and user account deleted successfully",
        "member_id": member_id
    }