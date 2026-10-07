from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.category import Category
from app.models.user import UserRole
from app.schemas.category import CategoryCreate, CategoryResponse
from app.auth.dependencies import require_role


router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)


# =========================================================
# CREATE CATEGORY - ADMIN ONLY
# =========================================================

@router.post(
    "",
    response_model=CategoryResponse,
    status_code=201
)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.Admin))
):
    existing = db.scalar(
        select(Category).where(
            Category.name == data.name
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Category already exists"
        )

    category = Category(
        **data.model_dump()
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


# =========================================================
# LIST CATEGORIES - PUBLIC
# =========================================================

@router.get(
    "",
    response_model=list[CategoryResponse]
)
def list_categories(
    db: Session = Depends(get_db)
):
    categories = db.scalars(
        select(Category)
        .order_by(Category.id.asc())
    ).all()

    return categories


# =========================================================
# UPDATE CATEGORY - ADMIN ONLY
# =========================================================

@router.put(
    "/{category_id}",
    response_model=CategoryResponse
)
def update_category(
    category_id: int,
    data: CategoryCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.Admin))
):
    category = db.get(Category, category_id)

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    existing = db.scalar(
        select(Category).where(
            Category.name == data.name,
            Category.id != category_id
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Category already exists"
        )

    category.name = data.name

    db.commit()
    db.refresh(category)

    return category


# =========================================================
# DELETE CATEGORY - ADMIN ONLY
# =========================================================
@router.delete(
    "/{category_id}",
    status_code=200
)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.Admin))
):
    category = db.get(Category, category_id)

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    # Don't delete category if products are using it
    if category.products:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete category with products"
        )

    category_name = category.name

    db.delete(category)
    db.commit()

    return {
        "message": "Category deleted successfully",
        "category_id": category_id,
        "category_name": category_name
    }