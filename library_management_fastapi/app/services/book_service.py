from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.category import Category

from app.schemas.book import (
    BookCreate,
    BookUpdate
)


# =========================================================
# CREATE BOOK
# =========================================================

def create_book(
    db: Session,
    data: BookCreate
):

    # Check category
    category = db.query(Category).filter(
        Category.category_id == data.category_id
    ).first()

    if category is None:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    # Check ISBN
    existing_book = db.query(Book).filter(
        Book.isbn == data.isbn
    ).first()

    if existing_book:
        raise HTTPException(
            status_code=409,
            detail="ISBN already exists"
        )

    # Validate copies
    if data.available_copies > data.total_copies:

        raise HTTPException(
            status_code=400,
            detail="Available copies cannot exceed total copies"
        )

    if data.available_copies < 0:

        raise HTTPException(
            status_code=400,
            detail="Available copies cannot be less than zero"
        )

    if data.total_copies < 0:

        raise HTTPException(
            status_code=400,
            detail="Total copies cannot be less than zero"
        )

    # Create book
    book = Book(
        title=data.title,
        author=data.author,
        isbn=data.isbn,
        category_id=data.category_id,
        total_copies=data.total_copies,
        available_copies=data.available_copies,
        published_year=data.published_year
    )

    db.add(book)

    db.commit()

    db.refresh(book)

    return book


# =========================================================
# GET ALL BOOKS
# =========================================================

def get_books(
    db: Session,
    title=None,
    author=None,
    category_id=None,
    skip=0,
    limit=10
):

    query = db.query(Book)

    # Search by title
    if title:

        query = query.filter(
            Book.title.ilike(f"%{title}%")
        )

    # Search by author
    if author:

        query = query.filter(
            Book.author.ilike(f"%{author}%")
        )

    # Filter by category
    if category_id:

        query = query.filter(
            Book.category_id == category_id
        )

    return query.offset(
        skip
    ).limit(
        limit
    ).all()


# =========================================================
# GET BOOK BY ID
# =========================================================

def get_book(
    db: Session,
    book_id: int
):

    book = db.query(Book).filter(
        Book.book_id == book_id
    ).first()

    if book is None:

        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    return book


# =========================================================
# UPDATE BOOK
# =========================================================

def update_book(
    db: Session,
    book_id: int,
    data: BookUpdate
):

    book = db.query(Book).filter(
        Book.book_id == book_id
    ).first()

    if book is None:

        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    # Update title
    if data.title is not None:
        book.title = data.title

    # Update author
    if data.author is not None:
        book.author = data.author

    # Update ISBN
    if data.isbn is not None:

        existing_book = db.query(Book).filter(
            Book.isbn == data.isbn,
            Book.book_id != book_id
        ).first()

        if existing_book:

            raise HTTPException(
                status_code=409,
                detail="ISBN already exists"
            )

        book.isbn = data.isbn

    # Update category
    if data.category_id is not None:

        category = db.query(Category).filter(
            Category.category_id == data.category_id
        ).first()

        if category is None:

            raise HTTPException(
                status_code=404,
                detail="Category not found"
            )

        book.category_id = data.category_id

    # Update total copies
    if data.total_copies is not None:

        if data.total_copies < 0:

            raise HTTPException(
                status_code=400,
                detail="Total copies cannot be less than zero"
            )

        borrowed_copies = (
            book.total_copies -
            book.available_copies
        )

        if data.total_copies < borrowed_copies:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Total copies cannot be less than "
                    "currently borrowed copies"
                )
            )

        book.total_copies = data.total_copies

        book.available_copies = (
            data.total_copies -
            borrowed_copies
        )

    # Update available copies
    if data.available_copies is not None:

        if data.available_copies < 0:

            raise HTTPException(
                status_code=400,
                detail="Available copies cannot be less than zero"
            )

        if data.available_copies > book.total_copies:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Available copies cannot exceed "
                    "total copies"
                )
            )

        book.available_copies = data.available_copies

    # Update published year
    if data.published_year is not None:
        book.published_year = data.published_year

    db.commit()

    db.refresh(book)

    return book


# =========================================================
# DELETE BOOK
# =========================================================

def delete_book(
    db: Session,
    book_id: int
):

    book = db.query(Book).filter(
        Book.book_id == book_id
    ).first()

    if book is None:

        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    # Import here to avoid circular imports
    from app.models.borrow import BorrowRecord

    # Check active borrowing
    active_borrow = db.query(
        BorrowRecord
    ).filter(
        BorrowRecord.book_id == book_id,
        BorrowRecord.status.in_(
            ["Borrowed", "Overdue"]
        )
    ).first()

    if active_borrow:

        raise HTTPException(
            status_code=400,
            detail="Cannot delete a currently borrowed book"
        )

    db.delete(book)

    db.commit()

    return True