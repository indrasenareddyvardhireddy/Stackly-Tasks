from datetime import datetime, timedelta
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SLAPolicy
from app.models.enums import Priority

# (first response minutes, resolution minutes)
DEFAULT_SLA = {
    Priority.LOW: (24 * 60, 72 * 60),
    Priority.MEDIUM: (8 * 60, 48 * 60),
    Priority.HIGH: (2 * 60, 24 * 60),
    Priority.URGENT: (30, 8 * 60),
}


async def get_policy(db: AsyncSession, priority: Priority) -> SLAPolicy:
    res = await db.execute(select(SLAPolicy).where(SLAPolicy.priority == priority))
    policy = res.scalar_one_or_none()
    if policy is None:  # safety net if the seed rows are missing
        fr, rs = DEFAULT_SLA[priority]
        policy = SLAPolicy(priority=priority, first_response_minutes=fr, resolution_minutes=rs)
        db.add(policy)
        await db.flush()
    return policy


def compute_due_times(created_at: datetime, policy: SLAPolicy, paused_seconds: int = 0) -> Tuple[datetime, datetime]:
    first_response_due = created_at + timedelta(minutes=policy.first_response_minutes)
    resolution_due = created_at + timedelta(minutes=policy.resolution_minutes, seconds=paused_seconds)
    return first_response_due, resolution_due
