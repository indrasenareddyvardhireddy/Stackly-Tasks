"""
Creates demo data so you can test every role straight away:

    python -m app.utils.seed

Safe to run several times (existing records are skipped).
"""
from app.auth.security import hash_password
from app.database import SessionLocal
from app.models.enums import Role, SeatCategory
from app.models.user import User
from app.models.venue import Screen, Venue
from app.services.venue_service import create_seats_bulk

USERS = [
    ("Admin User", "admin@example.com", "9000000001", "Admin@123", Role.ADMIN),
    ("Olivia Organizer", "organizer@example.com", "9000000002", "Organizer@123", Role.ORGANIZER),
    ("Charlie Customer", "customer@example.com", "9000000003", "Customer@123", Role.CUSTOMER),
    ("Chitra Customer", "customer2@example.com", "9000000004", "Customer@123", Role.CUSTOMER),
]


def main():
    db = SessionLocal()
    try:
        for name, email, phone, password, role in USERS:
            if not db.query(User).filter(User.email == email).first():
                db.add(User(name=name, email=email, phone=phone, password_hash=hash_password(password),
                            role=role.value, is_active=True, is_approved=True))
        db.commit()

        venue = db.query(Venue).filter(Venue.name == "PVR Cinemas - Banjara Hills").first()
        if not venue:
            venue = Venue(name="PVR Cinemas - Banjara Hills", city="Hyderabad",
                          address="Road No. 12, Banjara Hills, Hyderabad", is_active=True)
            db.add(venue)
            db.commit()
            db.refresh(venue)
            screen = Screen(venue_id=venue.id, name="Screen 1", total_seats=0)
            db.add(screen)
            db.commit()
            db.refresh(screen)
            create_seats_bulk(db, screen, "A", "E", 12, SeatCategory.SILVER.value)
            create_seats_bulk(db, screen, "F", "H", 12, SeatCategory.GOLD.value)
            create_seats_bulk(db, screen, "I", "J", 8, SeatCategory.RECLINER.value)

        if not db.query(User).filter(User.email == "staff@example.com").first():
            db.add(User(name="Gate Staff", email="staff@example.com", phone="9000000005",
                        password_hash=hash_password("Staff@123"), role=Role.STAFF.value,
                        is_active=True, is_approved=True, venue_id=venue.id))
            db.commit()
        print("Seed complete.")
        print("  admin@example.com      / Admin@123")
        print("  organizer@example.com  / Organizer@123  (already approved)")
        print("  customer@example.com   / Customer@123")
        print("  customer2@example.com  / Customer@123")
        print("  staff@example.com      / Staff@123      (assigned to PVR Cinemas - Banjara Hills)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
