import os
os.environ.setdefault("DATABASE_URL","sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY","test-secret")
os.environ.setdefault("SMTP_USERNAME","");os.environ.setdefault("SMTP_PASSWORD","")
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.database import Base,get_db
from app.main import app
engine=create_engine("sqlite+pysqlite:///:memory:",connect_args={"check_same_thread":False})
TestingSession=sessionmaker(bind=engine)
Base.metadata.create_all(engine)

def override_db():
    db=TestingSession()
    try:yield db
    finally:db.close()
app.dependency_overrides[get_db]=override_db
@pytest.fixture
def client():return TestClient(app)
