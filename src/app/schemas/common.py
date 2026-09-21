"""Shared response structures for record collection endpoints."""

from typing import Generic, TypeVar

from pydantic import Field

from app.models.base import CamelModel

T = TypeVar("T")


# 以下为待手写区域：PageParams（现有实现为参考，实际改写后再标记为手写）
class PageParams(CamelModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
# 待手写区域结束：PageParams


# 以下为待手写区域：PageData（现有实现为参考，实际改写后再标记为手写）
class PageData(CamelModel, Generic[T]):
    list: list[T]
    total: int = Field(ge=0)
    has_more: bool
# 待手写区域结束：PageData
