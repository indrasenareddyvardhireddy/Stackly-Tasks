"""Seed sample data:  python -m app.utils.seed   (run AFTER `alembic upgrade head`)"""
from datetime import time, timedelta

from app.auth.security import hash_password
from app.database import SessionLocal
from app.models import (Address, Coupon, DeliveryPartner, MenuCategory, MenuItem, Restaurant, User)
from app.utils.timeutil import now

PW = "Password@123"


def user(db, name, email, role, approved=True):
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(name=name, email=email, phone="9876543210", password_hash=hash_password(PW), role=role,
                 is_approved=approved)
        db.add(u)
        db.flush()
    return u


def main():
    db = SessionLocal()
    admin = user(db, "Admin", "admin@example.com", "admin")
    owner = user(db, "Ravi Owner", "owner@example.com", "restaurant_owner")
    cust = user(db, "Asha Customer", "customer@example.com", "customer")
    partners = [(user(db, "Pavan Partner", "partner1@example.com", "delivery_partner"), "TS09AB1234", 17.4470, 78.3890),
                (user(db, "Kiran Partner", "partner2@example.com", "delivery_partner"), "TS09CD5678", 17.4600, 78.4000)]
    for u, veh, lat, lng in partners:
        if not u.partner_profile:
            db.add(DeliveryPartner(user_id=u.id, vehicle_type="Bike", vehicle_number=veh, is_approved=True,
                                   is_online=True, current_latitude=lat, current_longitude=lng,
                                   last_location_at=now()))
    if not db.query(Address).filter(Address.customer_id == cust.id).first():
        db.add(Address(customer_id=cust.id, label="Home", address_line="Gachibowli, Hyderabad", city="Hyderabad",
                       pincode="500032", latitude=17.4486, longitude=78.3908, is_default=True))
    if not db.query(Restaurant).filter(Restaurant.owner_id == owner.id).first():
        specs = [("Spice Garden Biryani", "Biryani", "Gachibowli Main Rd", 17.4500, 78.3900, 25,
                  [("Biryanis", [("Chicken Dum Biryani", 299, False, 15), ("Veg Biryani", 219, True, 10)]),
                   ("Starters", [("Chicken 65", 199, False, 10), ("Paneer Tikka", 189, True, 10)])]),
                 ("Dosa Corner", "South Indian", "Madhapur Road", 17.4400, 78.3800, 15,
                  [("Tiffins", [("Masala Dosa", 99, True, 5), ("Idli (3 pcs)", 59, True, 5)])])]
        for name, cuisine, addr, lat, lng, prep, cats in specs:
            r = Restaurant(owner_id=owner.id, name=name, cuisine_type=cuisine, address=addr, latitude=lat,
                           longitude=lng, opening_time=time(0, 0), closing_time=time(23, 59),
                           delivery_radius_km=5, min_order_value=99, avg_preparation_minutes=prep)
            db.add(r)
            db.flush()
            for cname, items in cats:
                c = MenuCategory(restaurant_id=r.id, name=cname)
                db.add(c)
                db.flush()
                for iname, price, veg, pack in items:
                    db.add(MenuItem(restaurant_id=r.id, category_id=c.id, name=iname, price=price, is_veg=veg,
                                    packaging_charge=pack // 5))
        db.flush()
        biryani = db.query(Restaurant).filter(Restaurant.name == "Spice Garden Biryani").first()
        t = now()
        db.add_all([
            Coupon(code="WELCOME50", description="Rs.50 off on your first order", discount_type="Flat",
                   discount_value=50, min_order_value=199, valid_from=t - timedelta(days=1),
                   valid_to=t + timedelta(days=365), per_user_limit=1, first_order_only=True, created_by=admin.id),
            Coupon(code="BIRYANI20", description="20% off at Spice Garden (max Rs.100)", discount_type="Percentage",
                   discount_value=20, max_discount=100, min_order_value=299, restaurant_id=biryani.id,
                   valid_from=t - timedelta(days=1), valid_to=t + timedelta(days=365), total_usage_limit=100,
                   per_user_limit=5, created_by=owner.id),
            Coupon(code="FLAT100", description="Rs.100 off above Rs.499", discount_type="Flat", discount_value=100,
                   min_order_value=499, valid_from=t - timedelta(days=1), valid_to=t + timedelta(days=365),
                   created_by=admin.id)])
    db.commit()
    db.close()
    print("Seeded. All accounts use password:", PW)


if __name__ == "__main__":
    main()
