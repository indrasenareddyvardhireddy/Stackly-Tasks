import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.jobs.scheduler import shutdown_scheduler, start_scheduler
from app.routers import agents, auth, categories, feedback, messages, notifications, reports, sla, tickets
from app.websockets import chat as chat_ws
from app.websockets import notifications as notifications_ws

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()  # SLA check, escalation and auto-close jobs start with the app
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Real-Time Support Ticket System",
    description="Tickets, auto-assignment, live chat, notifications, SLA tracking and reports.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

for r in (auth, agents, categories, sla, tickets, messages, feedback, notifications, reports):
    app.include_router(r.router)
app.include_router(chat_ws.router)
app.include_router(notifications_ws.router)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "Duplicate or conflicting data"})


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "docs": "/docs", "chat_test": "/chat-test"}


@app.get("/chat-test", include_in_schema=False)
async def chat_test_page():
    return FileResponse(STATIC_DIR / "chat_test.html")
