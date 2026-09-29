from typing import Optional
from app.auth.dependencies import get_current_user, get_current_admin
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db

from app.schemas.book import (
    BookCreate,
    BookUpdate,
    BookResponse
)

from app.services.book_service import (
    create_book,
    get_books,
    get_book,
    update_book,
    delete_book
)


router = APIRouter(
    prefix="/books",
    tags=["Books"]
)


@router.post(
    "",
    response_model=BookResponse,
    status_code=201
)
def add_book(
    data: BookCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):

    return create_book(
        db,
        data
    )


@router.get(
    "",
    response_model=list[BookResponse]
)
def list_books(

    title: Optional[str] = Query(
        None
    ),

    author: Optional[str] = Query(
        None
    ),

    category_id: Optional[int] = Query(
        None,
        gt=0
    ),

    skip: int = Query(
        0,
        ge=0
    ),

    limit: int = Query(
        10,
        ge=1,
        le=100
    ),

    db: Session = Depends(get_db)
):

    return get_books(
        db,
        title,
        author,
        category_id,
        skip,
        limit
    )


@router.get(
    "/{book_id}",
    response_model=BookResponse
)
def get_single_book(

    book_id: int,

    db: Session = Depends(get_db)
):

    return get_book(
        db,
        book_id
    )


@router.put(
    "/{book_id}",
    response_model=BookResponse
)
def edit_book(

    book_id: int,

    data: BookUpdate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):

    return update_book(
        db,
        book_id,
        data
    )


@router.delete(
    "/{book_id}",
    status_code=200
)
def remove_book(
    book_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    delete_book(
        db,
        book_id
    )

    return {
        "message": "Book deleted successfully",
        "book_id": book_id
    }