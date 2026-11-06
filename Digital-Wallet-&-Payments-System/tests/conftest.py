import os
import tempfile
import uuid

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["DEBUG_RETURN_OTP"] = "true"
os.environ["SMTP_HOST"] = ""
os.environ["STATEMENTS_DIR"] = os.path.join(_tmp, "statements")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app, seed_admin  # noqa: E402
from app.services.ledger import ensure_system_accounts  # noqa: E402

_counter = {"n": 0}


@pytest.fixture(autouse=True)
def fresh_db():
    # Tests only: production schema comes from Alembic, never create_all.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    ensure_system_accounts(db)
    seed_admin(db)
    db.close()
    _counter["n"] = 0
    yield


@pytest.fixture
def client():
    return TestClient(app)


def idem():
    return {"Idempotency-Key": str(uuid.uuid4())}


class Actor:
    def __init__(self, client, headers, phone, email):
        self.c, self.h, self.phone, self.email = client, headers, phone, email

    def post(self, url, json=None, key=None, **kw):
        h = dict(self.h)
        h["Idempotency-Key"] = key or str(uuid.uuid4())
        return self.c.post(url, json=json, headers=h, **kw)

    def get(self, url, **kw):
        return self.c.get(url, headers=self.h, **kw)

    def put(self, url, json=None, **kw):
        return self.c.put(url, json=json, headers=self.h, **kw)

    def send_otp(self, purpose):
        r = self.c.post("/otp/send", json={"purpose": purpose}, headers=self.h)
        assert r.status_code == 200, r.text
        return r.json()["otp"]

    @property
    def balance(self):
        return self.get("/wallet").json()["balance"]


def make_actor(client, role="User", funds=None, pin="2846"):
    _counter["n"] += 1
    n = _counter["n"]
    phone = f"98000000{n:02d}"
    email = f"{role.lower()}{n}@test.com"
    body = {"full_name": f"{role} {n}", "email": email, "phone": phone, "password": "Passw0rd1", "role": role}
    if role == "Merchant":
        body.update(business_name=f"Shop {n}", business_category="Groceries")
    assert client.post("/auth/register", json=body).status_code == 201
    token = client.post("/auth/login", json={"email": email, "password": "Passw0rd1"}).json()["access_token"]
    a = Actor(client, {"Authorization": f"Bearer {token}"}, phone, email)
    assert a.post("/wallet/pin", json={"pin": pin}).status_code == 201
    if funds:
        r = a.post("/wallet/add-money", {"amount": str(funds), "source": "UPI"})
        assert r.status_code == 201, r.text
    return a


@pytest.fixture
def admin(client):
    token = client.post("/auth/login", json={"email": "admin@wallet.local", "password": "Admin@12345"}).json()["access_token"]
    return Actor(client, {"Authorization": f"Bearer {token}"}, "9000000000", "admin@wallet.local")


def upgrade_kyc(admin, actor, pan):
    r = actor.post("/kyc", {"pan_number": pan, "aadhaar_last4": "1234", "full_name": "Test User", "date_of_birth": "1995-01-01"})
    assert r.status_code == 201, r.text
    assert admin.put(f"/admin/kyc/{r.json()['id']}/approve").status_code == 200
