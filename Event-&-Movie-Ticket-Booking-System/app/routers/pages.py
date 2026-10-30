from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import settings

router = APIRouter(tags=["Test pages"])


@router.get("/seat-map-test", include_in_schema=True)
def seat_map_test_page():
    """Simple HTML page that draws the live seat map (see README)."""
    return FileResponse(settings.STATIC_DIR / "seat_map_test.html")


@router.get("/razorpay-test")
def razorpay_test_page():
    """Page that opens Razorpay Checkout for a booking (test mode)."""
    return FileResponse(settings.STATIC_DIR / "razorpay_test.html")


