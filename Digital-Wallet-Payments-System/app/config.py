import os
from dotenv import load_dotenv

load_dotenv()


def _bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/wallet_db")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "Wallet App <no-reply@wallet.local>")
    SMTP_USE_TLS = _bool(os.getenv("SMTP_USE_TLS", "true"))

    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@wallet.local")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@12345")
    ADMIN_PHONE = os.getenv("ADMIN_PHONE", "9000000000")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Platform Admin")

    STATEMENTS_DIR = os.getenv("STATEMENTS_DIR", "statements")
    DEBUG_RETURN_OTP = _bool(os.getenv("DEBUG_RETURN_OTP", "false"))
    ENABLE_SCHEDULER = _bool(os.getenv("ENABLE_SCHEDULER", "true"))


settings = Settings()
