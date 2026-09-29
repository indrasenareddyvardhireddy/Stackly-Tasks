from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.users import User
from app.schemas.member import MemberCreate, MemberUpdate
from app.auth.jwt import hash_password


# =========================================================
# CREATE MEMBER + LOGIN ACCOUNT
# =========================================================

def create_member(db: Session, data: MemberCreate):

    # Check username
    existing_user = db.query(User).filter(
        User.username == data.username
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username already exists"
        )

    # Check user email
    existing_user_email = db.query(User).filter(
        User.email == data.email
    ).first()

    if existing_user_email:
        raise HTTPException(
            status_code=409,
            detail="User email already exists"
        )

    # Check member email
    existing_member = db.query(Member).filter(
        Member.email == data.email
    ).first()

    if existing_member:
        raise HTTPException(
            status_code=409,
            detail="Member email already exists"
        )

    try:

        # Create User login account
        user = User(
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            role="User",
            is_active=data.is_active
        )

        db.add(user)

        # Get generated user_id
        db.flush()

        # Create Member profile
        member = Member(
            user_id=user.user_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
            address=data.address,
            membership_date=data.membership_date or date.today(),
            is_active=data.is_active
        )

        db.add(member)

        db.commit()

        db.refresh(member)

        return member

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to create member and user account"
        )


# =========================================================
# GET ALL MEMBERS
# =========================================================

def get_members(
    db: Session,
    skip: int = 0,
    limit: int = 10
):

    return db.query(Member).offset(skip).limit(limit).all()


# =========================================================
# GET MEMBER
# =========================================================

def get_member(
    db: Session,
    member_id: int
):

    member = db.query(Member).filter(
        Member.member_id == member_id
    ).first()

    if member is None:
        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )

    return member


# =========================================================
# UPDATE MEMBER
# =========================================================

def update_member(
    db: Session,
    member_id: int,
    data: MemberUpdate
):

    member = get_member(db, member_id)

    if data.email is not None:

        existing_member = db.query(Member).filter(
            Member.email == data.email,
            Member.member_id != member_id
        ).first()

        if existing_member:
            raise HTTPException(
                status_code=409,
                detail="Member email already exists"
            )

        existing_user = db.query(User).filter(
            User.email == data.email,
            User.user_id != member.user_id
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="User email already exists"
            )

        member.email = data.email

        if member.user:
            member.user.email = data.email

    if data.name is not None:
        member.name = data.name

    if data.phone is not None:
        member.phone = data.phone

    if data.address is not None:
        member.address = data.address

    if data.is_active is not None:
        member.is_active = data.is_active

        if member.user:
            member.user.is_active = data.is_active

    db.commit()
    db.refresh(member)

    return member


# =========================================================
# DELETE MEMBER
# =========================================================

def delete_member(
    db: Session,
    member_id: int
):

    member = get_member(db, member_id)

    user = member.user

    db.delete(member)

    if user:
        db.delete(user)

    db.commit()

    return True