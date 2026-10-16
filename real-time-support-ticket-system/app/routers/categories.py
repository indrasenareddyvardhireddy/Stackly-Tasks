from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models import Category, Ticket, User
from app.models.enums import FINISHED_STATUSES, Role
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["Categories"])
admin_only = require_roles(Role.ADMIN)


async def _name_taken(db: AsyncSession, name: str, exclude_id: int = 0) -> bool:
    res = await db.execute(select(Category.id).where(Category.category_name == name, Category.id != exclude_id))
    return res.first() is not None


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(data: CategoryCreate, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    if await _name_taken(db, data.category_name):
        raise HTTPException(status_code=409, detail="Category name already exists")
    cat = Category(category_name=data.category_name, description=data.description, is_active=data.is_active)
    db.add(cat)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Category name already exists")
    return cat


@router.get("", response_model=List[CategoryOut], summary="List categories (customers/agents see only active ones)")
async def list_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Category)
    if user.role != Role.ADMIN:
        stmt = stmt.where(Category.is_active.is_(True))
    return (await db.execute(stmt.order_by(Category.id).offset(skip).limit(limit))).scalars().all()


@router.put("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int, data: CategoryUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    cat = await db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    fields = data.model_dump(exclude_unset=True)
    if fields.get("category_name") and await _name_taken(db, fields["category_name"], category_id):
        raise HTTPException(status_code=409, detail="Category name already exists")
    for key, value in fields.items():
        if value is not None or key == "description":
            setattr(cat, key, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Category name already exists")
    return cat


@router.delete("/{category_id}")
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    cat = await db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    open_count = (
        await db.execute(
            select(func.count(Ticket.id)).where(Ticket.category_id == category_id, Ticket.status.notin_(FINISHED_STATUSES))
        )
    ).scalar_one()
    if open_count:
        raise HTTPException(status_code=400, detail=f"Category has {open_count} open ticket(s) and cannot be deleted")
    total = (await db.execute(select(func.count(Ticket.id)).where(Ticket.category_id == category_id))).scalar_one()
    if total:
        # historical tickets still reference it, so deactivate instead of hard delete
        cat.is_active = False
        await db.commit()
        return {"detail": "Category has historical tickets; it was deactivated instead of deleted"}
    await db.delete(cat)
    await db.commit()
    return {"detail": "Category deleted"}
