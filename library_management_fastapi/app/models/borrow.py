from sqlalchemy import Column, Integer, Date, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class BorrowRecord(Base):

    __tablename__ = "borrow_records"

    borrow_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    book_id = Column(
        Integer,
        ForeignKey("books.book_id"),
        nullable=False,
        index=True
    )

    member_id = Column(
        Integer,
        ForeignKey("members.member_id"),
        nullable=False,
        index=True
    )

    borrow_date = Column(
        Date,
        nullable=False
    )

    due_date = Column(
        Date,
        nullable=False
    )

    return_date = Column(
        Date,
        nullable=True
    )

    status = Column(
        String(20),
        nullable=False,
        default="Borrowed"
    )

    book = relationship(
        "Book",
        back_populates="borrow_records"
    )

    member = relationship(
        "Member",
        back_populates="borrow_records"
    )