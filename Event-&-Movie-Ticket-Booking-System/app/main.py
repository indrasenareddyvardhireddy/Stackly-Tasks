import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.routers import (admin, auth, bookings, cancellations, events, pages, payments, reports, seats,
                         tickets, venues, webhooks)
from app.websockets import expiry_listener, seat_ws
from app.websockets.manager import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.set_loop(asyncio.get_running_loop())     # lets worker threads push websocket messages
    settings.TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    expiry_listener.enable_keyspace_notifications()
    expiry_listener.start_expiry_listener()
    start_scheduler()                                # jobs start automatically with the app
    yield
    stop_scheduler()
    expiry_listener.stop_expiry_listener()


app = FastAPI(
    title="Event & Movie Ticket Booking System",
    description="Seat locking with Redis, live seat map over WebSockets, QR tickets, refunds, waitlist and reports.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    # unique-constraint races (email, booking number, seat) surface as a clean 409
    return JSONResponse(status_code=409, content={"detail": "Conflict: the request violates a uniqueness rule"})


for module in (auth, admin, venues, events, seats, bookings, payments, tickets, cancellations, reports, pages, webhooks):
    app.include_router(module.router)
app.include_router(seat_ws.router)


@app.get("/", tags=["Health"])
def root():
    return {"app": "Event & Movie Ticket Booking System", "docs": "/docs", "seat_map_test": "/seat-map-test"}
