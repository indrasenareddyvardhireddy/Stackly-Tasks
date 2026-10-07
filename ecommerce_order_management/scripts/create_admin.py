from getpass import getpass
from sqlalchemy import select
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.utils.security import hash_password

def main():
    db = SessionLocal()
    try:
        print("=== Manual Admin Creation ===")
        username = input("Admin username: ").strip()
        email = input("Admin email: ").strip()
        password = getpass("Admin password: ")

        if not username or not email or not password:
            print("All fields are required.")
            return
        if db.scalar(select(User).where(User.username == username)):
            print("Username already exists.")
            return
        if db.scalar(select(User).where(User.email == email)):
            print("Email already exists.")
            return

        db.add(User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.Admin,
            is_active=True
        ))
        db.commit()
        print(f"Admin '{username}' created successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
