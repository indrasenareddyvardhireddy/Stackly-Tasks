from decimal import Decimal
from typing import Annotated, Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer

T = TypeVar("T")

# Decimal in the code, plain JSON number in responses
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    total: int
    skip: int
    limit: int
    items: List[T]


class MessageResponse(BaseModel):
    message: str
