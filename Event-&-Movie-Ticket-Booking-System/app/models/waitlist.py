from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class Waitlist(TimestampMixin, Base):
    __tablename__ = "waitlist"
    __table_args__ = (UniqueConstraint("show_id", "customer_id", name="uq_waitlist_show_customer"),)

    id = Column(Integer, primary_key=True)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seats_requested = Column(Integer, nullable=False)
    category = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="Waiting")
    notified_at = Column(DateTime, nullable=True)

    show = relationship("Show", back_populates="waitlist")
    customer = relationship("User")

    @property
    def customer_name(self) -> str:
        return self.customer.name
