"""Slice a filtered record sequence into a frontend page."""

from collections.abc import Sequence
from typing import TypeVar

from app.schemas.common import PageData

T = TypeVar("T")


def paginate(rows: Sequence[T], page: int, page_size: int) -> PageData[T]:
    offset = (page - 1) * page_size
    items = list(rows[offset:offset + page_size])
    return PageData[T](list=items, total=len(rows), has_more=offset + len(items) < len(rows))
