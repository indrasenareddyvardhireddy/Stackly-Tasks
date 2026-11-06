from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

_kwargs = {"pool_pre_ping": True}
if settings.DATABASE_URL.startswith("mysql"):
    # READ COMMITTED: after a row lock is granted, later SELECTs (limit sums,
    # fraud counts) see the latest committed data instead of an old snapshot.
    _kwargs["isolation_level"] = "READ COMMITTED"
    _kwargs["pool_size"] = 10
    _kwargs["max_overflow"] = 20
if settings.DATABASE_URL.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.DATABASE_URL, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
