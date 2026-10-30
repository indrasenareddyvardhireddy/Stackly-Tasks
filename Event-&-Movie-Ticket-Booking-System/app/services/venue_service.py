from typing import List

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.venue import Screen, Seat
from app.utils.helpers import row_range


def create_seats_bulk(db: Session, screen: Screen, row_start: str, row_end: str,
                      seats_per_row: int, category: str) -> List[Seat]:
    rows = row_range(row_start, row_end)
    existing = {(s.row_label, s.seat_number) for s in
                db.query(Seat.row_label, Seat.seat_number).filter(
                    Seat.screen_id == screen.id, Seat.row_label.in_(rows)).all()}
    wanted = [(row, n) for row in rows for n in range(1, seats_per_row + 1)]
    clash = [f"{r}{n}" for r, n in wanted if (r, n) in existing]
    if clash:
        raise HTTPException(status_code=409, detail=(
            f"Seats already exist on this screen: {', '.join(clash[:10])}{' ...' if len(clash) > 10 else ''}"))
    seats = [Seat(screen_id=screen.id, row_label=r, seat_number=n, category=category, is_active=True)
             for r, n in wanted]
    db.add_all(seats)
    db.flush()
    screen.total_seats = db.query(func.count(Seat.id)).filter(Seat.screen_id == screen.id).scalar()
    db.commit()
    return seats
