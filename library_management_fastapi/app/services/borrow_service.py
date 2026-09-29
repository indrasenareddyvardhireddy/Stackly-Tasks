from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.member import Member
from app.models.borrow import BorrowRecord


def borrow_book(
    db: Session,
    data
):

    book = db.get(
        Book,
        data.book_id
    )

    if not book:

        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    member = db.get(
        Member,
        data.member_id
    )

    if not member:

        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )

    # Inactive member
    if not member.is_active:

        raise HTTPException(
            status_code=400,
            detail="Inactive members cannot borrow books"
        )

    # Maximum 3 active books
    active_borrows = (
        db.query(BorrowRecord)
        .filter(
            BorrowRecord.member_id
            == member.member_id,

            BorrowRecord.status.in_(
                ["Borrowed", "Overdue"]
            )
        )
        .all()
    )

    if len(active_borrows) >= 3:

        raise HTTPException(
            status_code=400,
            detail="A member cannot borrow more than 3 books at a time"
        )

    # Same book cannot be borrowed twice
    existing_borrow = (
        db.query(BorrowRecord)
        .filter(
            BorrowRecord.member_id
            == member.member_id,

            BorrowRecord.book_id
            == book.book_id,

            BorrowRecord.status.in_(
                ["Borrowed", "Overdue"]
            )
        )
        .first()
    )

    if existing_borrow:

        raise HTTPException(
            status_code=409,
            detail="Member has already borrowed this book"
        )

    # Check available copies
    if book.available_copies <= 0:

        raise HTTPException(
            status_code=400,
            detail="No available copies for this book"
        )

    borrow_date = (
        data.borrow_date
        if data.borrow_date
        else date.today()
    )

    due_date = (
        borrow_date
        + timedelta(days=14)
    )

    borrow_record = BorrowRecord(

        book_id=book.book_id,

        member_id=member.member_id,

        borrow_date=borrow_date,

        due_date=due_date,

        status="Borrowed"
    )

    book.available_copies -= 1

    db.add(borrow_record)

    db.commit()

    db.refresh(borrow_record)

    return borrow_record


def return_book(
    db: Session,
    borrow_id: int
):

    borrow_record = db.get(
        BorrowRecord,
        borrow_id
    )

    if not borrow_record:

        raise HTTPException(
            status_code=404,
            detail="Borrow record not found"
        )

    if borrow_record.status == "Returned":

        raise HTTPException(
            status_code=400,
            detail="Book has already been returned"
        )

    book = db.get(
        Book,
        borrow_record.book_id
    )

    return_date = date.today()

    borrow_record.return_date = return_date

    # Determine whether it was late
    if return_date > borrow_record.due_date:

        borrow_record.status = "Overdue"

    else:

        borrow_record.status = "Returned"

    # Once physically returned, transaction is closed.
    borrow_record.status = "Returned"

    if book:

        book.available_copies = min(
            book.available_copies + 1,
            book.total_copies
        )

    db.commit()

    db.refresh(borrow_record)

    return borrow_record


def get_member_books(
    db: Session,
    member_id: int
):

    member = db.get(
        Member,
        member_id
    )

    if not member:

        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )

    records = (
        db.query(BorrowRecord)
        .filter(
            BorrowRecord.member_id
            == member_id,

            BorrowRecord.status.in_(
                ["Borrowed", "Overdue"]
            )
        )
        .all()
    )

    # Update overdue records
    today = date.today()

    changed = False

    for record in records:

        if (
            record.status == "Borrowed"
            and today > record.due_date
        ):

            record.status = "Overdue"

            changed = True

    if changed:

        db.commit()

    return records


def get_book_history(
    db: Session,
    book_id: int
):

    book = db.get(
        Book,
        book_id
    )

    if not book:

        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    return (
        db.query(BorrowRecord)
        .filter(
            BorrowRecord.book_id
            == book_id
        )
        .order_by(
            BorrowRecord.borrow_date.desc()
        )
        .all()
    )


def get_overdue_books(
    db: Session
):

    today = date.today()

    records = (
        db.query(BorrowRecord)
        .filter(
            BorrowRecord.status
            == "Borrowed"
        )
        .all()
    )

    for record in records:

        if today > record.due_date:

            record.status = "Overdue"

    db.commit()

    return (
        db.query(BorrowRecord)
        .filter(
            BorrowRecord.status
            == "Overdue"
        )
        .all()
    )