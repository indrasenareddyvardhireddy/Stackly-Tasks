"""QR signing, PDF ticket generation, gate scanning and entry statistics."""
import os
from datetime import timedelta
from io import BytesIO
from typing import Optional

import qrcode
from fastapi import HTTPException
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.booking import Booking, Ticket
from app.models.enums import BookingStatus, ShowStatus
from app.models.event import Show
from app.models.user import User
from app.utils.qr import sign_value, verify_value
from app.utils.time import now


def make_qr_value(booking_number: str) -> str:
    return sign_value(booking_number, settings.QR_SECRET_KEY)


def pdf_full_path(filename: str) -> str:
    return str(settings.TICKETS_DIR / filename)


def generate_ticket_pdf(ctx: dict, qr_value: str) -> str:
    """Creates tickets/<booking_number>.pdf and returns the file NAME."""
    os.makedirs(settings.TICKETS_DIR, exist_ok=True)
    filename = f"{ctx['booking_number']}.pdf"

    qr_img = qrcode.make(qr_value)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)

    c = canvas.Canvas(pdf_full_path(filename), pagesize=A4)
    width, height = A4
    c.setTitle(f"Ticket {ctx['booking_number']}")

    c.setFillColorRGB(0.1, 0.1, 0.35)
    c.rect(0, height - 90, width, 90, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(40, height - 55, "E-TICKET")
    c.setFont("Helvetica", 12)
    c.drawRightString(width - 40, height - 55, ctx["booking_number"])

    c.setFillColorRGB(0, 0, 0)
    y = height - 140
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, y, ctx["event_title"][:55])
    y -= 40
    rows = [
        ("Venue", ctx["venue_name"]),
        ("Screen", ctx["screen_name"]),
        ("Date & Time", ctx["show_datetime"]),
        ("Seats", f"{ctx['seats']}  ({ctx['seat_count']} ticket(s))"),
        ("Customer", ctx["customer_name"]),
        ("Booking No.", ctx["booking_number"]),
        ("Amount Paid", f"Rs. {ctx['amount']}"),
    ]
    for label, value in rows:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, f"{label}:")
        c.setFont("Helvetica", 12)
        c.drawString(150, y, str(value)[:70])
        y -= 26

    qr_size = 200
    c.drawImage(ImageReader(buf), (width - qr_size) / 2, y - qr_size - 20, width=qr_size, height=qr_size)
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, y - qr_size - 38, "Scan this QR code at the entry gate. Valid for one entry only.")
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width / 2, 40, "Entry opens 1 hour before the show. Convenience fee and GST are non-refundable.")
    c.showPage()
    c.save()
    return filename


def get_or_create_pdf(booking: Booking, ctx: dict, db: Session) -> str:
    """Full path of the ticket PDF (regenerated if the file went missing)."""
    ticket = booking.ticket
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not ticket.pdf_path or not os.path.exists(pdf_full_path(ticket.pdf_path)):
        ticket.pdf_path = generate_ticket_pdf(ctx, ticket.qr_value)
        db.commit()
    return pdf_full_path(ticket.pdf_path)


def scan_ticket(db: Session, staff: User, qr_value: str) -> dict:
    booking_number = verify_value(qr_value, settings.QR_SECRET_KEY)
    if not booking_number:
        raise HTTPException(status_code=400, detail="Invalid QR code (signature check failed)")

    booking = db.query(Booking).filter(Booking.booking_number == booking_number).first()
    if not booking or booking.ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if booking.status != BookingStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail=f"Ticket rejected: booking is {booking.status}")

    show = booking.show
    if show.screen.venue_id != staff.venue_id:
        raise HTTPException(status_code=403, detail="This ticket is for a show at a different venue")
    if show.status == ShowStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="Ticket rejected: show is cancelled")

    t = now()
    if t < show.start_at - timedelta(minutes=settings.SCAN_OPEN_MINUTES_BEFORE):
        raise HTTPException(status_code=400, detail="Scanning opens 1 hour before the show starts")
    if t > show.end_at:
        raise HTTPException(status_code=400, detail="The show has ended")

    ticket = booking.ticket
    if ticket.is_used:
        raise HTTPException(status_code=409, detail=f"Ticket already used at {ticket.used_at.strftime('%d %b %Y %I:%M:%S %p')}")

    # atomic "mark used" so two simultaneous scans cannot both succeed
    updated = (db.query(Ticket).filter(Ticket.id == ticket.id, Ticket.is_used.is_(False))
               .update({"is_used": True, "used_at": t, "scanned_by": staff.id, "updated_at": t},
                       synchronize_session=False))
    db.commit()
    if not updated:
        db.refresh(ticket)
        raise HTTPException(status_code=409, detail=f"Ticket already used at {ticket.used_at.strftime('%d %b %Y %I:%M:%S %p')}")

    return {
        "message": "Entry allowed",
        "booking_number": booking.booking_number,
        "customer_name": booking.customer.name,
        "seats": [bs.label for bs in booking.seats],
        "seat_count": booking.seat_count,
        "event_title": show.event.title,
        "screen_name": show.screen.name,
        "show_start": show.start_at,
        "scanned_at": t,
    }


def show_entries(db: Session, show_id: int) -> dict:
    confirmed = BookingStatus.CONFIRMED.value
    total_bookings, total_tickets = db.query(
        func.count(Booking.id), func.coalesce(func.sum(Booking.seat_count), 0)
    ).filter(Booking.show_id == show_id, Booking.status == confirmed).one()
    entered_bookings, entered_tickets = db.query(
        func.count(Booking.id), func.coalesce(func.sum(Booking.seat_count), 0)
    ).join(Ticket, Ticket.booking_id == Booking.id).filter(
        Booking.show_id == show_id, Booking.status == confirmed, Ticket.is_used.is_(True)).one()
    return {
        "show_id": show_id,
        "total_bookings": int(total_bookings),
        "entered_bookings": int(entered_bookings),
        "total_tickets": int(total_tickets),
        "entered_tickets": int(entered_tickets),
        "pending_entry_bookings": int(total_bookings) - int(entered_bookings),
    }
