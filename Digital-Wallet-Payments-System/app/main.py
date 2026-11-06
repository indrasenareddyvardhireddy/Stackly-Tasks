import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth.security import hash_secret
from app.config import settings
from app.database import SessionLocal
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.models import Role, User
from app.routers import admin, auth, bank, money_requests, payments, reports, transactions, transfers, wallet
from app.services.ledger import ensure_system_accounts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("wallet")


def seed_admin(db) -> None:
    """Admin accounts cannot be registered publicly, so one is seeded from .env."""
    if db.query(User).filter(User.role == Role.ADMIN).first():
        return
    db.add(User(full_name=settings.ADMIN_NAME, email=settings.ADMIN_EMAIL.lower(), phone=settings.ADMIN_PHONE,
                password_hash=hash_secret(settings.ADMIN_PASSWORD), role=Role.ADMIN, is_active=True))
    db.commit()
    logger.info("Seeded admin user %s", settings.ADMIN_EMAIL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        ensure_system_accounts(db)  # Bank Settlement, Cashback Pool, Fees, Withdrawal Clearing, Hold
        seed_admin(db)
    finally:
        db.close()
    if settings.ENABLE_SCHEDULER:
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Digital Wallet & Payments System", version="1.0.0",
              description="Double-entry ledger wallet: P2P, merchant QR payments, refunds, cashback, withdrawals.",
              lifespan=lifespan)

for r in (auth.router, wallet.router, admin.router, transfers.router, payments.router, money_requests.router,
          bank.router, transactions.router, reports.router):
    app.include_router(r)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "service": "wallet-api"}
