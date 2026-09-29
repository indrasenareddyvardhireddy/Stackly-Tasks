from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)


class BookCreate(BaseModel):

    title: str = Field(
        ...,
        min_length=1,
        max_length=200
    )

    author: str = Field(
        ...,
        min_length=1,
        max_length=150
    )

    isbn: str = Field(
        ...,
        min_length=10,
        max_length=20
    )

    category_id: int = Field(
        ...,
        gt=0
    )

    total_copies: int = Field(
        ...,
        ge=1
    )

    available_copies: int = Field(
        ...,
        ge=0
    )

    published_year: Optional[int] = Field(
        None,
        ge=1000,
        le=2100
    )

    @field_validator("available_copies")
    @classmethod
    def validate_available_copies(cls, value, info):

        total = info.data.get("total_copies")

        if total is not None and value > total:
            raise ValueError(
                "available_copies cannot exceed total_copies"
            )

        return value


# =========================================================
# UPDATE BOOK
# =========================================================

class BookUpdate(BaseModel):

    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200
    )

    author: Optional[str] = Field(
        None,
        min_length=1,
        max_length=150
    )

    isbn: Optional[str] = Field(
        None,
        min_length=10,
        max_length=20
    )

    category_id: Optional[int] = Field(
        None,
        gt=0
    )

    total_copies: Optional[int] = Field(
        None,
        ge=1
    )

    available_copies: Optional[int] = Field(
        None,
        ge=0
    )

    published_year: Optional[int] = Field(
        None,
        ge=1000,
        le=2100
    )


# =========================================================
# BOOK RESPONSE
# =========================================================

class BookResponse(BookCreate):

    book_id: int

    model_config = ConfigDict(
        from_attributes=True
    )