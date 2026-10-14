from fastapi.testclient import TestClient
from app.main import app

def test_health():
    # Importing app requires a valid DATABASE_URL and JWT_SECRET_KEY in .env.
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
