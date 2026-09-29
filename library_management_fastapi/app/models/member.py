from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Member(Base):
    __tablename__ = "members"

    member_id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        unique=True,
        nullable=True
    )

    name = Column(
        String(100),
        nullable=False
    )

    email = Column(
        String(150),
        unique=True,
        nullable=False
    )

    phone = Column(
        String(15),
        nullable=False
    )

    address = Column(
        String(255),
        nullable=False
    )

    membership_date = Column(
        Date,
        nullable=False
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    # User <-> Member relationship
    user = relationship(
        "User",
        back_populates="member"
    )

    # Member <-> BorrowRecord relationship
    borrow_records = relationship(
        "BorrowRecord",
        back_populates="member"
    )