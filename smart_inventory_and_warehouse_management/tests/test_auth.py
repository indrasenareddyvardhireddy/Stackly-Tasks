from app.database import SessionLocal
from app.models import User
from app.auth.security import hash_password

def test_invalid_login(client):
    db=SessionLocal();db.add(User(username="seed",email="seed@example.com",password_hash=hash_password("Password@123"),role="Admin"));db.commit();db.close()
    r=client.post("/auth/login",json={"username":"seed","password":"bad"});assert r.status_code==401
