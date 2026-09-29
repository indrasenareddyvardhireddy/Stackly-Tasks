from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.category import Category


def create_category(
    db: Session,
    data
):

    existing = (
        db.query(Category)
        .filter(
            Category.category_name
            == data.category_name
        )
        .first()
    )

    if existing:

        raise HTTPException(
            status_code=409,
            detail="Category name already exists"
        )

    category = Category(
        category_name=data.category_name,
        description=data.description
    )

    db.add(category)

    db.commit()

    db.refresh(category)

    return category


def get_categories(
    db: Session,
    skip: int,
    limit: int
):

    return (
        db.query(Category)
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_category(
    db: Session,
    category_id: int,
    data
):

    category = db.get(
        Category,
        category_id
    )

    if not category:

        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    duplicate = (
        db.query(Category)
        .filter(
            Category.category_name
            == data.category_name,
            Category.category_id
            != category_id
        )
        .first()
    )

    if duplicate:

        raise HTTPException(
            status_code=409,
            detail="Category name already exists"
        )

    category.category_name = (
        data.category_name
    )

    category.description = (
        data.description
    )

    db.commit()

    db.refresh(category)

    return category


def delete_category(
    db: Session,
    category_id: int
):

    category = db.get(
        Category,
        category_id
    )

    if not category:

        raise HTTPException(
            status_code=404,
            detail="Category not found"
        )

    if category.books:

        raise HTTPException(
            status_code=409,
            detail="Cannot delete category because books exist in this category"
        )

    db.delete(category)

    db.commit()