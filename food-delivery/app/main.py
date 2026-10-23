import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.jobs.scheduler import build_scheduler
from app.routers import addresses, auth, cart, coupons, orders, partners, ratings, reports, restaurants, ws
from app.websockets.manager import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.loop = asyncio.get_running_loop()  # lets sync code push WebSocket messages
    scheduler = build_scheduler()
    scheduler.start()  # jobs start automatically with the app
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Food Delivery System", version="1.0.0", lifespan=lifespan,
              description="Click **Authorize** and paste the access token from POST /auth/login.")

for module in (auth, restaurants, addresses, cart, coupons, orders, partners, ratings, reports, ws):
    app.include_router(module.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", tags=["Health"])
def root():
    return {"service": "Food Delivery System", "docs": "/docs", "tracking_test_page": "/tracking-test"}
