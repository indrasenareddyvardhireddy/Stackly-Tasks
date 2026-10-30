from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.enums import BookingStatus, Role
from app.models.event import Show
from app.models.user import User
from app.routers.bookings import get_booking_for_user
from app.schemas.ticket import EntriesResponse, ScanRequest, ScanResponse
from app.services import ticket_service
from app.services.booking_service import booking_context

router = APIRouter(tags=["Tickets & Entry"])


@router.get("/bookings/{booking_id}/ticket")
def download_ticket(booking_id: int, db: Session = Depends(get_db),
                    user: User = Depends(require_roles(Role.CUSTOMER))):
    booking = get_booking_for_user(db, booking_id, user)
    if booking.status != BookingStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail=f"No ticket available: booking is {booking.status}")
    path = ticket_service.get_or_create_pdf(booking, booking_context(booking), db)
    return FileResponse(path, media_type="application/pdf", filename=f"{booking.booking_number}.pdf")


@router.post("/tickets/scan", response_model=ScanResponse)
def scan_ticket(payload: ScanRequest, db: Session = Depends(get_db),
                staff: User = Depends(require_roles(Role.STAFF))):
    if staff.venue_id is None:
        raise HTTPException(status_code=403, detail="Staff account is not assigned to a venue")
    return ticket_service.scan_ticket(db, staff, payload.qr_value)


@router.get("/shows/{show_id}/entries", response_model=EntriesResponse)
def show_entries(show_id: int, db: Session = Depends(get_db),
                 user: User = Depends(require_roles(Role.STAFF, Role.ADMIN, Role.ORGANIZER))):
    show = db.get(Show, show_id)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    if user.role == Role.STAFF.value and show.screen.venue_id != user.venue_id:
        raise HTTPException(status_code=403, detail="This show is not at your assigned venue")
    if user.role == Role.ORGANIZER.value and show.event.organizer_id != user.id:
        raise HTTPException(status_code=403, detail="This is not your event")
    return ticket_service.show_entries(db, show_id)
