
from app.database import SessionLocal
from app.models import User
from app.auth.security import hash_password


def create_admin():
    db = SessionLocal()

    try:
        email = "admin@hospital.com"

        # Prevent duplicate admin accounts
        existing_user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing_user:
            print("Admin account already exists.")
            print(f"Email: {existing_user.email}")
            print(f"Role: {existing_user.role}")
            return

        admin = User(
            name="Hospital Admin",
            email=email,
            phone="9876543210",
            password_hash=hash_password("Admin@12345"),
            role="admin",
            is_active=True,
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("Admin created successfully!")
        print("Email: admin@hospital.com")
        print("Password: Admin@12345")
        print(f"Admin ID: {admin.id}")

    except Exception as error:
        db.rollback()
        print("Failed to create admin:", error)

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
