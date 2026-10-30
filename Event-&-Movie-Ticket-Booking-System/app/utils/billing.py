"""Pure bill calculation (no framework imports so it is easy to unit test)."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

CONVENIENCE_FEE_PER_TICKET = Decimal("30")
GST_RATE = Decimal("0.18")
_CENT = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


def calculate_bill(seat_prices: Iterable) -> dict:
    prices = [Decimal(p) for p in seat_prices]
    count = len(prices)
    ticket_total = sum(prices, Decimal("0"))
    fee = CONVENIENCE_FEE_PER_TICKET * count
    gst = money((ticket_total + fee) * GST_RATE)
    grand = money(ticket_total + fee + gst)
    return {
        "seat_count": count,
        "ticket_total": money(ticket_total),
        "convenience_fee": money(fee),
        "gst_amount": gst,
        "grand_total": grand,
    }
