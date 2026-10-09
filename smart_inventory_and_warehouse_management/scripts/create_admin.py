from app.database import SessionLocal
from app.models import User
from app.auth.security import hash_password

def main():
    db=SessionLocal()
    try:
        username="admin"; email="admin@example.com"; password="Admin@123"
        if db.query(User).filter(User.username==username).first(): print("Admin already exists"); return
        db.add(User(username=username,email=email,password_hash=hash_password(password),role="Admin",is_active=True));db.commit()
        print("Admin created: admin / Admin@123")
    finally: db.close()
if __name__=="__main__": main()
