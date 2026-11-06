from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import random
import string

from pydantic_core import to_jsonable_python

IST_OFFSET = timedelta(hours=5, minutes=30)
ZERO = Decimal("0.00")


def utcnow() -> datetime:
    """Naive UTC datetime (all timestamps are stored as UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def q2(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def jsonable(obj):
    """Decimal -> str (exact), datetime -> ISO, Enum -> value."""
    return to_jsonable_python(obj)


def inr(amount) -> str:
    amount = q2(amount)
    neg = amount < 0
    whole, frac = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    out = "\u20b9" + whole + ("" if frac == "00" else "." + frac)
    return "-" + out if neg else out


def mask_phone(phone) -> str:
    return ("XXXXXX" + phone[-4:]) if phone else ""


def mask_account(number: str) -> str:
    return "X" * max(len(number) - 4, 0) + number[-4:]


# ---- IST day / month boundaries (returned as naive UTC for DB comparison) ----
def ist_now() -> datetime:
    return utcnow() + IST_OFFSET


def ist_date_start_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day) - IST_OFFSET


def today_start_utc() -> datetime:
    return ist_date_start_utc(ist_now().date())


def month_start_utc(year: int, month: int) -> datetime:
    return ist_date_start_utc(date(year, month, 1))


def next_month(year: int, month: int):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def to_ist(dt: datetime) -> datetime:
    return dt + IST_OFFSET


def random_token(n=6) -> str:
    return "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(n))
