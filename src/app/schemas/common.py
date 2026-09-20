"""Shared response structures for record collection endpoints."""

from typing import Generic, TypeVar

from pydantic import Field

from app.models.base import CamelModel

T = TypeVar("T")


class PageParams(CamelModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)


class PageData(CamelModel, Generic[T]):
    list: list[T]
    total: int = Field(ge=0)
    has_more: bool
