from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int


class PageResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PageMeta
