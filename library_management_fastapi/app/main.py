from fastapi import FastAPI

from app.database import Base, engine

# =========================================================
# MODELS
# =========================================================

from app.models.category import Category
from app.models.book import Book
from app.models.member import Member
from app.models.borrow import BorrowRecord
from app.models.users import User


# =========================================================
# ROUTERS
# =========================================================

from app.routers.categories import (
    router as category_router
)

from app.routers.books import (
    router as book_router
)

from app.routers.members import (
    router as member_router
)

from app.routers.borrow import (
    router as borrow_router
)

from app.routers.auth import (
    router as auth_router
)


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

Base.metadata.create_all(
    bind=engine
)


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="Library Management System",
    description=(
        "Library Management System using "
        "FastAPI, SQLAlchemy and MySQL"
    ),
    version="1.0.0"
)


# =========================================================
# AUTHENTICATION
# =========================================================

app.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"]
)


# =========================================================
# CATEGORIES
# =========================================================

app.include_router(
    category_router,
    prefix="/categories",
    tags=["Categories"]
)


# =========================================================
# BOOKS
# =========================================================

app.include_router(
    book_router,
    prefix="/books",
    tags=["Books"]
)


# =========================================================
# MEMBERS
# =========================================================

app.include_router(
    member_router,
    prefix="/members",
    tags=["Members"]
)


# =========================================================
# BORROW / RETURN
# =========================================================

app.include_router(
    borrow_router,
    prefix="/borrow",
    tags=["Borrow / Return"]
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "message": "Library Management System API is running"
    }