from datetime import date

from pydantic import BaseModel


class BorrowCreate(BaseModel):
    book_id: int
    member_id: int
    borrow_date: date | None = None


class BorrowResponse(BaseModel):
    borrow_id: int
    book_id: int
    member_id: int
    borrow_date: date
    due_date: date
    return_date: date | None
    status: str

    class Config:
        from_attributes = True