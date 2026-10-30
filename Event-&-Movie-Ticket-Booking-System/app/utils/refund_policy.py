"""Customer cancellation policy (pure functions)."""
from decimal import Decimal
from typing import Optional

from app.utils.billing import money

FULL_REFUND = Decimal("1.00")
HALF_REFUND = Decimal("0.50")


def refund_percentage(hours_before_show: float) -> Optional[Decimal]:
    """> 24h -> 100%, 2h..24h -> 50%, < 2h -> None (cancellation not allowed)."""
    if hours_before_show > 24:
        return FULL_REFUND
    if hours_before_show >= 2:
        return HALF_REFUND
    return None


def customer_refund_amount(ticket_total, hours_before_show: float) -> Optional[Decimal]:
    pct = refund_percentage(hours_before_show)
    if pct is None:
        return None
    # convenience fee and its GST are never refunded on customer cancellations
    return money(Decimal(ticket_total) * pct)
