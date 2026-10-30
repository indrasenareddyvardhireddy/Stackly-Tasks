import os
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    # --- infrastructure (from .env) ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/ticket_booking")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
    QR_SECRET_KEY: str = os.getenv("QR_SECRET_KEY", os.getenv("JWT_SECRET_KEY", "dev-qr-secret-change-me"))
    JWT_ALGORITHM: str = "HS256"

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "Ticket Booking <no-reply@example.com>")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

    # Razorpay (test mode keys start with rzp_test_). Leave empty to use only the mock payment.
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    TICKETS_DIR: Path = BASE_DIR / os.getenv("TICKETS_DIR", "tickets")
    STATIC_DIR: Path = BASE_DIR / "static"

    # --- business rules ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    LOCK_TTL_SECONDS: int = 600            # 10 minutes
    MAX_SEATS_PER_SHOW: int = 10
    CONVENIENCE_FEE_PER_TICKET: Decimal = Decimal("30")
    GST_RATE: Decimal = Decimal("0.18")
    CLEANING_GAP_MINUTES: int = 15
    BOOKING_CLOSE_MINUTES: int = 30
    SCAN_OPEN_MINUTES_BEFORE: int = 60
    EVENT_CACHE_TTL_SECONDS: int = 300
    LOCK_RATE_LIMIT_PER_MINUTE: int = 5
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 5


settings = Settings()
