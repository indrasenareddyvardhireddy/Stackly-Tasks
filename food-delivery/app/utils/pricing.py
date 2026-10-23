import math
from datetime import datetime
from typing import Optional

PLATFORM_FEE = 5.0
GST_RATE = 0.05
BASE_DELIVERY_FEE = 20.0
BASE_DELIVERY_KM = 3
EXTRA_PER_KM = 8.0
SURGE_MULTIPLIER = 1.5
PARTNER_BASE = 25.0
PARTNER_PER_KM = 6.0


def is_peak_hour(at: Optional[datetime] = None) -> bool:
    """Bonus: surge pricing 12-14 and 19-22."""
    h = (at or datetime.now()).hour
    return 12 <= h < 14 or 19 <= h < 22


def delivery_fee(distance_km: float, at: Optional[datetime] = None) -> float:
    fee = BASE_DELIVERY_FEE
    if distance_km > BASE_DELIVERY_KM:
        fee += EXTRA_PER_KM * math.ceil(distance_km - BASE_DELIVERY_KM)
    if is_peak_hour(at):
        fee *= SURGE_MULTIPLIER
    return round(fee, 2)


def partner_earning(distance_km: float, tip: float = 0.0) -> float:
    return round(PARTNER_BASE + PARTNER_PER_KM * distance_km + (tip or 0), 2)


def calculate_bill(item_total, discount, packaging, distance_km, tip=0.0, at=None) -> dict:
    taxable = item_total - discount
    gst = round(taxable * GST_RATE, 2)
    fee = delivery_fee(distance_km, at)
    grand = round(taxable + packaging + fee + PLATFORM_FEE + gst + (tip or 0), 2)
    return {
        "item_total": round(item_total, 2), "discount_amount": round(discount, 2),
        "packaging_charges": round(packaging, 2), "delivery_fee": fee,
        "platform_fee": PLATFORM_FEE, "gst_amount": gst,
        "tip_amount": round(tip or 0, 2), "grand_total": grand,
    }
