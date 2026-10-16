import enum
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TicketStatusHistory


def _v(x):
    return x.value if isinstance(x, enum.Enum) else x


async def add_history(
    db: AsyncSession,
    ticket_id: int,
    event_type: str,
    old=None,
    new=None,
    changed_by: Optional[int] = None,
    note: Optional[str] = None,
) -> None:
    db.add(
        TicketStatusHistory(
            ticket_id=ticket_id,
            event_type=event_type,
            old_status=_v(old),
            new_status=_v(new),
            changed_by=changed_by,
            note=note,
        )
    )
