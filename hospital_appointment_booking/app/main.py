from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import auth, departments, doctors, appointments, consultations, queue, reports, admin
from app.jobs.scheduler import start_scheduler, stop_scheduler
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("uploads",exist_ok=True)
    start_scheduler()
    yield
    stop_scheduler()

app=FastAPI(title="Hospital Appointment Booking System",version="1.0.0",lifespan=lifespan,description="Hospital appointments, consultation records and live queues.")
for router in [auth.router,departments.router,doctors.router,appointments.router,consultations.router,queue.router,reports.router,admin.router]:
    app.include_router(router)

@app.get("/")
def root():
    return {"message":"Hospital Appointment Booking API","docs":"/docs","health":"/health"}

@app.get("/health")
def health():
    return {"status":"ok"}
