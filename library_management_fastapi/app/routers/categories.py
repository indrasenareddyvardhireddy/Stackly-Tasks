from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_admin
from app.database import get_db

from app.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse
)

from app.services.category_service import (
    create_category,
    get_categories,
    update_category,
    delete_category
)


router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=201
)
def add_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
    
):

    return create_category(
        db,
        data
    )


@router.get(
    "",
    response_model=list[CategoryResponse]
)
def list_categories(

    skip: int = Query(
        0,
        ge=0
    ),

    limit: int = Query(
        10,
        ge=1,
        le=100
    ),

    db: Session = Depends(get_db)
):

    return get_categories(
        db,
        skip,
        limit
    )


@router.put(
    "/{category_id}",
    response_model=CategoryResponse
)
def edit_category(

    category_id: int,

    data: CategoryUpdate,

    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):

    return update_category(
        db,
        category_id,
        data
    )


@router.delete(
    "/{category_id}",
    status_code=200
)
def remove_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    delete_category(
        db,
        category_id
    )

    return {
        "message": "Category deleted successfully",
        "category_id": category_id
    }