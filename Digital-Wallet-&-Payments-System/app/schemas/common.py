import re
from decimal import Decimal
from typing import Annotated

from fastapi import Query
from pydantic import AfterValidator, BaseModel, Field, StringConstraints

# amount > 0, at most 2 decimal places (and fits DECIMAL(12,2))
Amount = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Phone = Annotated[str, StringConstraints(pattern=r"^\d{10}$")]
Pin = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]
Otp = Annotated[str, StringConstraints(pattern=r"^\d{6}$")]


class Page:
    def __init__(self, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
        self.skip = skip
        self.limit = limit


def paginated(items, total, page: Page):
    return {"total": total, "skip": page.skip, "limit": page.limit, "items": items}


class Message(BaseModel):
    message: str
