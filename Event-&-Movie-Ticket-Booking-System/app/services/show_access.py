from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.enums import EventStatus, Role
from app.models.event import Show
from app.models.user import User


def get_visible_show(db: Session, show_id: int, user: User) -> Show:
    """Customers only see shows of Published events; admin/staff/owning organizer see everything."""
    show = db.get(Show, show_id)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    if user.role == Role.CUSTOMER.value and show.event.status != EventStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Show not found")
    if user.role == Role.ORGANIZER.value and show.event.organizer_id != user.id \
            and show.event.status != EventStatus.PUBLISHED.value:
        raise HTTPException(status_code=404, detail="Show not found")
    return show
