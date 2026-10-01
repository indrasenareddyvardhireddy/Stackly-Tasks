from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.departments import router as departments_router
from app.routers.employees import router as employees_router
from app.routers.leaves import (
    router as leaves_router,
    employees_leave_router,
)
from app.routers.reports import router as reports_router


app = FastAPI(
    title="Employee & Leave Management System",
    description=(
        "Employee and Leave Management System "
        "using FastAPI, SQLAlchemy and MySQL."
    ),
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Authentication
app.include_router(
    auth_router,
    prefix="/auth"
)


# Departments
app.include_router(
    departments_router,
    prefix="/departments"
)


# Employees
app.include_router(
    employees_router,
    prefix="/employees"
)


# Leaves
app.include_router(
    leaves_router,
    prefix="/leaves"
)


# Employee leave routes
app.include_router(
    employees_leave_router,
    prefix="/employees"
)


# Reports
app.include_router(
    reports_router,
    prefix="/reports"
)


@app.get("/")
def root():

    return {
        "message": (
            "Employee & Leave Management "
            "System API is running"
        ),
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
def health():

    return {
        "status": "ok"
    }