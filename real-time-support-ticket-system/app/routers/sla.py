from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models import SLAPolicy, User
from app.models.enums import Priority, Role
from app.schemas.category import SLAPolicyOut, SLAPolicyUpdate
from app.services.sla_service import DEFAULT_SLA, get_policy

router = APIRouter(prefix="/sla-policies", tags=["SLA Policies"])


@router.get("", response_model=List[SLAPolicyOut])
async def list_policies(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    for p in Priority:  # make sure every priority has a row
        await get_policy(db, p)
    await db.commit()
    rows = (await db.execute(select(SLAPolicy))).scalars().all()
    order = list(DEFAULT_SLA.keys())
    return sorted(rows, key=lambda r: order.index(r.priority))


@router.put("/{priority}", response_model=SLAPolicyOut)
async def update_policy(
    priority: Priority, data: SLAPolicyUpdate, db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMIN)),
):
    """Changes apply to tickets created (or re-prioritised) after the update."""
    policy = await get_policy(db, priority)
    policy.first_response_minutes = data.first_response_minutes
    policy.resolution_minutes = data.resolution_minutes
    await db.commit()
    return policy
