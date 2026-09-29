from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Book(Base):

    __tablename__ = "books"

    book_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    title = Column(
        String(200),
        nullable=False,
        index=True
    )

    author = Column(
        String(150),
        nullable=False,
        index=True
    )

    isbn = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True
    )

    category_id = Column(
        Integer,
        ForeignKey("categories.category_id"),
        nullable=False
    )

    total_copies = Column(
        Integer,
        nullable=False
    )

    available_copies = Column(
        Integer,
        nullable=False
    )

    published_year = Column(
        Integer,
        nullable=True
    )

    category = relationship(
        "Category",
        back_populates="books"
    )

    borrow_records = relationship(
        "BorrowRecord",
        back_populates="book"
    )