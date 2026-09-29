from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import (
    get_current_admin,
    get_member_access
)
from app.schemas.borrow import BorrowCreate, BorrowResponse
from app.services.borrow_service import (
    borrow_book,
    return_book,
    get_member_books,
    get_book_history,
    get_overdue_books
)

router = APIRouter()


# =========================================================
# BORROW BOOK - ADMIN ONLY
# =========================================================

@router.post(
    "/borrow",
    response_model=BorrowResponse,
    status_code=201
)
def borrow(
    data: BorrowCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    return borrow_book(db, data)


# =========================================================
# RETURN BOOK - ADMIN ONLY
# =========================================================

@router.put(
    "/return/{borrow_id}",
    response_model=BorrowResponse
)
def return_book_api(
    borrow_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    return return_book(db, borrow_id)


# =========================================================
# MEMBER'S BORROWED BOOKS
# USER CAN VIEW OWN RECORDS
# ADMIN CAN VIEW ANY MEMBER
# =========================================================

@router.get(
    "/members/{member_id}/books",
    response_model=list[BorrowResponse]
)
def member_books(
    member_id: int,
    db: Session = Depends(get_db),
    member=Depends(get_member_access)
):
    return get_member_books(db, member_id)


# =========================================================
# BOOK BORROW HISTORY - ADMIN ONLY
# =========================================================

@router.get(
    "/books/{book_id}/borrow-history",
    response_model=list[BorrowResponse]
)
def book_borrow_history(
    book_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    return get_book_history(db, book_id)


# =========================================================
# OVERDUE BOOKS - ADMIN ONLY
# =========================================================

@router.get(
    "/overdue",
    response_model=list[BorrowResponse]
)
def overdue_books(
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    return get_overdue_books(db)